import { describe, expect, it, vi } from 'vitest'
import { fetchSpeech, pickBrowserVoice, resetSpeechCache } from './tts.js'
import { createSpeechDetector, rmsOf } from './vad.js'
import { downsample, encodeWav } from './wav.js'

const FRAME_MS = 50
// 소리 크기 목록을 넣고 나온 신호를 [몇 번째 조각, 신호] 로 모은다
function run(detector, levels, speaking = false) {
  const events = []
  levels.forEach((rms, i) => {
    const e = detector.push(rms, FRAME_MS, { speaking })
    if (e) events.push([i, e])
  })
  return events
}
const repeat = (rms, ms) => Array(Math.round(ms / FRAME_MS)).fill(rms)

describe('createSpeechDetector: 말하면 바로 듣기', () => {
  it('조용하다가 목소리가 0.3초 이어지면 시작, 1초 조용하면 끝', () => {
    const d = createSpeechDetector()
    const events = run(d, [...repeat(0.005, 1000), ...repeat(0.1, 800), ...repeat(0.005, 1200)])
    expect(events.map(([, e]) => e)).toEqual(['start', 'end'])
    // 목소리 시작(20번째 조각) 후 0.3초(6조각) 안에 시작 신호
    expect(events[0][0]).toBeLessThanOrEqual(20 + 6)
  })

  it('짧은 소리(기침·물건 소리 0.1초)는 말로 보지 않는다', () => {
    const d = createSpeechDetector()
    expect(run(d, [...repeat(0.005, 1000), ...repeat(0.2, 100), ...repeat(0.005, 1000)])).toEqual([])
  })

  it('말 중간에 잠깐 쉬어도(0.5초) 끝내지 않는다', () => {
    const d = createSpeechDetector()
    const events = run(d, [...repeat(0.005, 500), ...repeat(0.1, 600), ...repeat(0.005, 500), ...repeat(0.1, 600), ...repeat(0.005, 1100)])
    expect(events.map(([, e]) => e)).toEqual(['start', 'end'])
  })

  it('시끄러운 곳에서는 소음보다 확실히 큰 소리만 말로 본다', () => {
    const d = createSpeechDetector()
    // 소음 0.03 이 계속 → 0.05 정도는 말로 안 봄, 0.2(소음의 4배 이상)는 말로 봄
    expect(run(d, [...repeat(0.03, 2000), ...repeat(0.05, 500)])).toEqual([])
    expect(run(d, repeat(0.2, 400)).map(([, e]) => e)).toEqual(['start'])
  })

  it('키오스크가 말하는 중에는 기준이 높아서 스피커 소리(0.04)로는 시작하지 않는다', () => {
    const d = createSpeechDetector()
    run(d, repeat(0.005, 1000))
    expect(run(d, repeat(0.04, 1000), true)).toEqual([])
    expect(run(d, repeat(0.2, 300), true).map(([, e]) => e)).toEqual(['start'])
  })

  it('14초가 넘으면 끊어서 보내고, 계속 말하면 새로 듣는다 (서버는 15초까지)', () => {
    const d = createSpeechDetector()
    const events = run(d, [...repeat(0.005, 500), ...repeat(0.1, 15000)])
    expect(events.slice(0, 3).map(([, e]) => e)).toEqual(['start', 'end', 'start'])
    const [[startAt], [endAt]] = events
    expect((endAt - startAt) * FRAME_MS).toBeLessThanOrEqual(14000)
  })
})

describe('wav: 서버로 보낼 녹음 파일', () => {
  it('rmsOf: 소리 크기', () => {
    expect(rmsOf(new Float32Array([0.5, -0.5, 0.5, -0.5]))).toBeCloseTo(0.5)
    expect(rmsOf(new Float32Array(0))).toBe(0)
  })

  it('48kHz 를 16kHz 로 줄인다', () => {
    expect(downsample(new Float32Array(4800), 48000).length).toBe(1600)
  })

  it('16kHz·16bit·모노 WAV 머리말과 길이', async () => {
    const blob = encodeWav([new Float32Array(48000)], 48000) // 1초
    expect(blob.type).toBe('audio/wav')
    expect(blob.size).toBe(44 + 16000 * 2)
    const view = new DataView(await blob.arrayBuffer())
    const text = (o) => String.fromCharCode(...[0, 1, 2, 3].map((i) => view.getUint8(o + i)))
    expect(text(0)).toBe('RIFF')
    expect(text(8)).toBe('WAVE')
    expect(view.getUint16(22, true)).toBe(1) // 모노
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint16(34, true)).toBe(16)
  })
})

describe('주변 소음보다 확실히 큰 말만', () => {
  it('소음의 4배가 안 되는 소리(옆 사람 말소리 등)는 무시한다', () => {
    const d = createSpeechDetector()
    run(d, repeat(0.02, 2000)) // 매장 소음
    expect(run(d, repeat(0.06, 1000))).toEqual([]) // 소음의 3배 → 무시
    expect(run(d, repeat(0.25, 400)).map(([, e]) => e)).toEqual(['start']) // 키오스크 앞 손님의 또렷한 목소리 → 인식
  })

  it('조용한 방이어도 너무 작은 소리(0.025)는 무시한다', () => {
    const d = createSpeechDetector()
    run(d, repeat(0.002, 1000))
    expect(run(d, repeat(0.025, 1000))).toEqual([])
  })

  it('0.2초짜리 큰 소리(문 닫는 소리 등)는 무시한다', () => {
    const d = createSpeechDetector()
    expect(run(d, [...repeat(0.005, 1000), ...repeat(0.3, 200), ...repeat(0.005, 1000)])).toEqual([])
  })
})

describe('안내 음성 (lib/tts.js)', () => {
  const blobRes = (ok = true, status = 200) => ({ ok, status, blob: async () => new Blob(['mp3']) })

  it('같은 문장은 서버에 다시 묻지 않는다', async () => {
    resetSpeechCache()
    const fetchImpl = vi.fn(async () => blobRes())
    await fetchSpeech('포장하세요?', { fetchImpl })
    await fetchSpeech('포장하세요?', { fetchImpl })
    expect(fetchImpl).toHaveBeenCalledTimes(1)
  })

  it('서버 음성이 실패하면 1분 동안은 바로 브라우저 목소리로 (서버에 안 물음)', async () => {
    resetSpeechCache()
    let t = 1000
    const now = () => t
    const fetchImpl = vi.fn(async () => blobRes(false, 503))
    await expect(fetchSpeech('a', { fetchImpl, now })).rejects.toThrow()
    await expect(fetchSpeech('b', { fetchImpl, now })).rejects.toThrow('TTS_DOWN')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    t += 61000
    fetchImpl.mockImplementation(async () => blobRes())
    await expect(fetchSpeech('c', { fetchImpl, now })).resolves.toBeInstanceOf(Blob)
  })

  it('브라우저 목소리는 가장 사람 같은 한국어 목소리를 고른다', () => {
    const voices = [
      { name: 'Microsoft Heami - Korean', lang: 'ko-KR' },
      { name: 'Google US English', lang: 'en-US' },
      { name: 'Microsoft SunHi Online (Natural) - Korean (Korea)', lang: 'ko-KR' },
    ]
    expect(pickBrowserVoice(voices).name).toContain('Natural')
    expect(pickBrowserVoice([{ name: 'Microsoft Heami - Korean', lang: 'ko-KR' }]).name).toContain('Heami')
    expect(pickBrowserVoice([{ name: 'Samantha', lang: 'en-US' }])).toBeNull()
  })
})


describe('말 시작 감지: 첫소리가 작거나 음절 사이가 잠깐 작아져도', () => {
  it('짧게(0.15초 이하) 작아진 건 이어진 말로 보고 늦지 않게 시작한다', () => {
    const d = createSpeechDetector()
    for (let i = 0; i < 20; i++) d.push(0.005, 50) // 조용한 방
    // 큰 소리 0.1초 → 0.1초 작아짐("포" 뒤) → 큰 소리 0.2초 : 예전엔 작아질 때 처음부터 다시 세서 더 늦게 시작
    const seq = [0.2, 0.2, 0.005, 0.005, 0.2, 0.2, 0.2, 0.2]
    const events = seq.map((v) => d.push(v, 50))
    expect(events.indexOf('start')).toBe(7) // 큰 소리 합 0.3초가 되는 순간
  })

  it('길게(0.15초 넘게) 조용하면 처음부터 다시 센다 (짧은 잡음 두 번은 말이 아님)', () => {
    const d = createSpeechDetector()
    for (let i = 0; i < 20; i++) d.push(0.005, 50)
    const seq = [0.2, 0.2, 0.005, 0.005, 0.005, 0.005, 0.2, 0.2]
    expect(seq.map((v) => d.push(v, 50))).not.toContain('start')
  })
})
