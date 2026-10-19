// 말 감지: 마이크 소리 크기(RMS)를 조금씩 넣으면 "말 시작"·"말 끝"을 알려 준다.
// 버튼을 누르지 않아도 손님이 말하면 바로 듣고, 말을 멈추면 바로 보내기 위한 것.
export const VAD_DEFAULTS = {
  minStart: 0.03, // 말 시작으로 볼 최소 소리 크기 (조용한 방이어도 이보다 커야 함)
  startFactor: 4, // 주변 소음보다 이만큼(4배) 커야 말로 본다 → 주변 소음·옆 사람 대화는 무시
  endFactor: 1.8, // 주변 소음의 이만큼 아래로 내려가면 조용하다고 본다
  bargeInFactor: 3, // 키오스크가 말하는 중에는 기준을 더 높인다 (자기 목소리를 손님 말로 착각하지 않게)
  minSpeechMs: 300, // 이만큼 이어서 소리가 커야 말한 것으로 본다 (기침·물건 소리·짧은 잡음 거르기)
  endSilenceMs: 1000, // 말한 뒤 이만큼 조용하면 말이 끝난 것으로 본다
  maxSpeechMs: 14000, // 서버는 15초까지만 받는다
}

export function createSpeechDetector(opts = {}) {
  const o = { ...VAD_DEFAULTS, ...opts }
  let floor = null // 주변 소음 크기 (말하지 않을 때 천천히 따라간다)
  let loudMs = 0
  let quietMs = 0
  let speechMs = 0
  let inSpeech = false

  return {
    get inSpeech() {
      return inSpeech
    },
    get floor() {
      return floor ?? 0
    },
    // rms: 이번 조각의 소리 크기, dtMs: 조각 길이, speaking: 키오스크가 안내를 읽는 중인지
    push(rms, dtMs, { speaking = false } = {}) {
      if (floor === null) floor = rms
      const start = Math.max(o.minStart, floor * o.startFactor) * (speaking ? o.bargeInFactor : 1)
      const end = Math.max(o.minStart * 0.6, floor * o.endFactor)

      if (!inSpeech) {
        // 주변 소음은 기준보다 작은 소리로만 배운다. 손님 목소리나 키오스크 안내 소리를 배우면 기준이 너무 높아짐
        if (!speaking && rms < start) floor = floor * 0.95 + rms * 0.05
        loudMs = rms >= start ? loudMs + dtMs : 0
        if (loudMs >= o.minSpeechMs) {
          inSpeech = true
          speechMs = loudMs
          quietMs = 0
          loudMs = 0
          return 'start'
        }
        return null
      }

      speechMs += dtMs
      quietMs = rms < end ? quietMs + dtMs : 0
      if (quietMs >= o.endSilenceMs || speechMs >= o.maxSpeechMs) {
        inSpeech = false
        quietMs = 0
        speechMs = 0
        return 'end'
      }
      return null
    },
    // 버튼으로 직접 시작·끝낼 때
    forceStart() {
      inSpeech = true
      speechMs = 0
      quietMs = 0
    },
    reset() {
      inSpeech = false
      loudMs = 0
      quietMs = 0
      speechMs = 0
    },
  }
}

// 소리 조각의 크기
export function rmsOf(samples) {
  let sum = 0
  for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i]
  return Math.sqrt(sum / (samples.length || 1))
}
