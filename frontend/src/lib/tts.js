// 안내 음성: 서버 /api/tts 의 사람 목소리(Google Chirp 3 HD)를 먼저 쓰고, 안 되면 브라우저 목소리 (PM 결정 2026-10-19 변경)
// - 받은 음성은 문장별로 저장해 두고 다시 쓴다 (같은 안내는 바로 나감)
// - 서버 음성이 실패하면 1분 동안은 바로 브라우저 목소리로 읽는다 (매번 기다리지 않게)
const TIMEOUT_MS = 4000
const DOWN_MS = 60000
const CACHE_MAX = 100

const cache = new Map() // 문장 → Blob
let downUntil = 0

// speed: 'normal' | 'slower' | 'faster' | 'louder' (손님이 "천천히 말해 줘" 등으로 고름)
export async function fetchSpeech(text, { fetchImpl = fetch, now = Date.now, speed = 'normal' } = {}) {
  const key = `${speed}|${text}`
  if (cache.has(key)) return cache.get(key)
  if (now() < downUntil) throw new Error('TTS_DOWN')
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    const res = await fetchImpl('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, speed }),
      signal: ctrl.signal,
    })
    if (!res.ok) throw new Error(`TTS ${res.status}`)
    const blob = await res.blob()
    cache.set(key, blob)
    if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value)
    return blob
  } catch (e) {
    downUntil = now() + DOWN_MS
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export function resetSpeechCache() {
  cache.clear()
  downUntil = 0
}

// 브라우저 목소리 중 가장 사람 같은 한국어 목소리 고르기 (Edge 의 "Natural", Chrome 의 Google 목소리 등)
const PREFERRED = [/natural/i, /online/i, /google/i, /sunhi|injoon|hyunsu/i]
export function pickBrowserVoice(voices) {
  const ko = (voices || []).filter((v) => /^ko/i.test(v.lang))
  for (const re of PREFERRED) {
    const v = ko.find((x) => re.test(x.name))
    if (v) return v
  }
  return ko[0] || null
}


// 브라우저 목소리로 읽을 때 빠르기 (서버 목소리와 같은 비율)
export const BROWSER_RATE = { normal: 0.9, slower: 0.77, faster: 1.04, louder: 0.83 }
