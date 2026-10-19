import { describe, expect, it } from 'vitest'
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
  it('조용하다가 목소리가 0.2초 이어지면 시작, 1초 조용하면 끝', () => {
    const d = createSpeechDetector()
    const events = run(d, [...repeat(0.005, 1000), ...repeat(0.1, 800), ...repeat(0.005, 1200)])
    expect(events.map(([, e]) => e)).toEqual(['start', 'end'])
    // 목소리 시작(20번째 조각) 후 0.2초(4조각) 안에 시작 신호
    expect(events[0][0]).toBeLessThanOrEqual(20 + 4)
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
    // 소음 0.03 이 계속 → 0.05 정도는 말로 안 봄, 0.15 는 말로 봄
    expect(run(d, [...repeat(0.03, 2000), ...repeat(0.05, 500)])).toEqual([])
    expect(run(d, repeat(0.15, 300)).map(([, e]) => e)).toEqual(['start'])
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
