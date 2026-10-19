// 마이크 소리 조각들을 서버(Whisper)가 바로 읽는 16kHz·16bit·모노 WAV 파일로 만든다.
export const WAV_RATE = 16000

export function downsample(samples, inputRate, outputRate = WAV_RATE) {
  if (inputRate === outputRate) return samples
  const ratio = inputRate / outputRate
  const out = new Float32Array(Math.floor(samples.length / ratio))
  for (let i = 0; i < out.length; i += 1) {
    // 구간 평균으로 줄인다 (단순히 건너뛰는 것보다 잡음이 적음)
    const from = Math.floor(i * ratio)
    const to = Math.min(samples.length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = from; j < to; j += 1) sum += samples[j]
    out[i] = sum / Math.max(1, to - from)
  }
  return out
}

export function concat(chunks) {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Float32Array(total)
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.length
  }
  return out
}

export function encodeWav(chunks, inputRate, outputRate = WAV_RATE) {
  const samples = downsample(concat(chunks), inputRate, outputRate)
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const write = (offset, text) => [...text].forEach((ch, i) => view.setUint8(offset + i, ch.charCodeAt(0)))
  write(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  write(8, 'WAVE')
  write(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt 크기
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // 모노
  view.setUint32(24, outputRate, true)
  view.setUint32(28, outputRate * 2, true) // 1초당 바이트
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  write(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}
