// 음성: 손님이 말하면 버튼 없이 바로 듣고, 말을 멈추면 바로 서버 /voice 로 보낸다 (PM 결정 2026-10-19: 다시 기본으로, #27 되돌림).
// 마이크 버튼을 누르면 직접 시작하고, 다시 눌러야 끝난다 (조용해도 자동으로 끝내지 않음).
// 음성 안내: 서버 /api/tts 의 사람 목소리(Google Chirp 3 HD)를 먼저, 안 되면 브라우저 목소리 중 가장 자연스러운 것 (PM 결정 2026-10-19 변경, lib/tts.js)
// - 주문 중에는 마이크를 계속 열어 두고 소리 크기만 본다. 주변 소음보다 4배 이상 큰 목소리가 0.3초 이어지면 녹음 시작(직전 1초 포함).
// - 1초 조용하면 녹음을 끝내 16kHz WAV로 보낸다(최대 14초). 안내를 읽는 중에 손님이 말하면 안내를 멈춘다(끼어들기).
// - 결제·응답 대기·안내 창에서는 멈춤(paused). 마이크 버튼으로도 직접 시작·끝낼 수 있다.
// - 끄려면 빌드할 때 VITE_HANDS_FREE=0 (버튼을 눌러 말하고 다시 눌러 끝내기만)
import { useCallback, useEffect, useRef, useState } from 'react'
import { BROWSER_RATE, fetchSpeech, pickBrowserVoice } from '../lib/tts.js'
import { createSpeechDetector, rmsOf } from '../lib/vad.js'
import { encodeWav } from '../lib/wav.js'

export const HANDS_FREE = import.meta.env.VITE_HANDS_FREE !== '0'
const PRE_ROLL_MS = 1000 // 말 시작으로 본 때보다 1초 앞부터 보낸다 (첫소리가 잘리면 "포장해" → "보장해"로 잘못 알아들음)
const BARGE_IN_PRE_ROLL_MS = 800 // 안내 중에 끼어들면 0.8초 (0.4초일 때 "불고기"의 "불"이 잘려 "치즈버거"로 인식됨, 2026-10-20 배포 녹음. 안내 중엔 시작 기준이 높아 감지가 늦음)
const FRAME_SIZE = 2048
const MANUAL_MAX_MS = 14000 // 버튼으로 시작했는데 끝 버튼을 안 누르면 14초에 보낸다 (서버 최대 15초)

export function useVoice({ onRecorded }) {
  // off: 마이크 닫힘 · waiting: 말하면 바로 들음 · listening: 듣는 중 · error: 마이크 없음/권한 없음
  const [micState, setMicState] = useState('off')
  const [speaking, setSpeaking] = useState(false)
  const onRecordedRef = useRef(onRecorded)
  onRecordedRef.current = onRecorded

  const audioRef = useRef(null) // { ctx, stream, proc }
  const detectorRef = useRef(createSpeechDetector())
  const preRollRef = useRef([]) // 직전 1초 소리 조각들
  const captureRef = useRef(null) // 듣는 중인 소리 조각들
  const manualRef = useRef(null) // 버튼으로 시작했으면 지금까지 들은 시간(ms). 조용해도 끝내지 않는다
  const pausedRef = useRef(true)
  const speakingRef = useRef(false)
  const utterRef = useRef(null)
  const speakTimerRef = useRef(null)
  const playerRef = useRef(null) // 지금 재생 중인 서버 음성 (Audio)
  const speakSeqRef = useRef(0) // 새 안내가 오면 이전 안내(받는 중인 음성 포함)는 버린다
  const speedRef = useRef('normal') // 안내 빠르기 ("천천히 말해 줘" → slower). 이번 주문 동안 유지

  const setSpeakingBoth = useCallback((value) => {
    speakingRef.current = value
    setSpeaking(value)
  }, [])

  const stopPlayback = useCallback(() => {
    speakSeqRef.current += 1
    clearTimeout(speakTimerRef.current)
    window.speechSynthesis?.cancel()
    const player = playerRef.current
    playerRef.current = null
    if (player) {
      player.pause()
      URL.revokeObjectURL(player.src)
    }
  }, [])

  const stopSpeaking = useCallback(() => {
    stopPlayback()
    setSpeakingBoth(false)
  }, [stopPlayback, setSpeakingBoth])

  const speak = useCallback(
    (text) => {
      if (!text) return
      stopPlayback()
      const seq = speakSeqRef.current
      const done = () => {
        if (seq !== speakSeqRef.current) return
        clearTimeout(speakTimerRef.current)
        playerRef.current = null
        setSpeakingBoth(false)
      }
      setSpeakingBoth(true) // 읽기 시작 전부터 '말하는 중'으로 본다
      speakTimerRef.current = setTimeout(done, 6000 + text.length * 300) // 끝 알림이 안 오는 경우 대비

      let fellBack = false
      const speakWithBrowser = () => {
        if (seq !== speakSeqRef.current || fellBack) return
        fellBack = true
        const synth = window.speechSynthesis
        if (!synth) return done()
        synth.cancel()
        const utter = new SpeechSynthesisUtterance(text)
        utter.lang = 'ko-KR'
        utter.rate = BROWSER_RATE[speedRef.current] ?? 0.9 // 어르신이 듣기 편하게 조금 천천히
        const voice = pickBrowserVoice(synth.getVoices())
        if (voice) utter.voice = voice
        utter.onend = done
        utter.onerror = done
        utterRef.current = utter // 일부 브라우저는 참조가 없으면 onend 를 안 부른다
        synth.speak(utter)
      }

      // 서버가 문장별 음성을 이어 붙인 WAV 하나를 준다 (고정 문장은 미리 만든 음성이라 빠름)
      fetchSpeech(text, { speed: speedRef.current })
        .then((blob) => {
          if (seq !== speakSeqRef.current) return
          const player = new Audio(URL.createObjectURL(blob))
          playerRef.current = player
          player.onended = () => {
            URL.revokeObjectURL(player.src)
            done()
          }
          player.onerror = speakWithBrowser
          return player.play()
        })
        .catch(speakWithBrowser) // 서버 음성이 없거나 재생이 막히면 브라우저 목소리
    },
    [stopPlayback, setSpeakingBoth],
  )

  const finishCapture = useCallback(() => {
    const audio = audioRef.current
    const chunks = captureRef.current
    captureRef.current = null
    manualRef.current = null
    detectorRef.current.reset()
    if (!audio || !chunks?.length) {
      if (audio) setMicState('waiting')
      return
    }
    setMicState('waiting')
    onRecordedRef.current(encodeWav(chunks, audio.ctx.sampleRate))
  }, [])

  const beginCapture = useCallback(() => {
    const pre = preRollRef.current
    let keep = pre.length
    if (speakingRef.current) {
      stopSpeaking() // 손님이 말하면 안내를 멈춘다
      const frameMs = pre.length ? (pre[0].length / (audioRef.current?.ctx.sampleRate || 48000)) * 1000 : 0
      keep = frameMs ? Math.ceil(BARGE_IN_PRE_ROLL_MS / frameMs) : pre.length
    }
    captureRef.current = pre.slice(-keep)
    setMicState('listening')
  }, [stopSpeaking])

  const onFrame = useCallback(
    (frame, sampleRate) => {
      const copy = new Float32Array(frame)
      const dtMs = (copy.length / sampleRate) * 1000

      // 직전 1초 보관 (첫 음절이 잘리지 않게)
      const pre = preRollRef.current
      pre.push(copy)
      while (pre.length * dtMs > PRE_ROLL_MS) pre.shift()

      if (captureRef.current) captureRef.current.push(copy)
      if (manualRef.current !== null) {
        manualRef.current += dtMs
        if (manualRef.current >= MANUAL_MAX_MS) finishCapture()
        return
      }
      if (pausedRef.current && !captureRef.current) return

      const event = detectorRef.current.push(rmsOf(copy), dtMs, { speaking: speakingRef.current })
      if (event === 'start' && !captureRef.current) beginCapture()
      else if (event === 'end' && captureRef.current) finishCapture()
    },
    [beginCapture, finishCapture],
  )

  // 마이크 열기 (주문 시작 버튼을 누른 뒤 부른다)
  const open = useCallback(async () => {
    if (audioRef.current) return
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!navigator.mediaDevices?.getUserMedia || !AudioCtx) {
      setMicState('error')
      return
    }
    try {
      // 에코 제거는 끈다: 안내 음성(HD 목소리)은 브라우저가 재생하므로, 켜 두면 안내가 나오는 동안·직후에
      // 손님 목소리까지 깎아 끼어들기가 안 되고 첫소리가 잘린다 ("포장해" → "보장해"). 안내 소리는 끼어들기 기준(vad.js)이 걸러 낸다.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true },
      })
      const ctx = new AudioCtx()
      await ctx.resume()
      const source = ctx.createMediaStreamSource(stream)
      // ScriptProcessor: 오래된 방식이지만 모든 브라우저에서 동작. 출력은 무음.
      const proc = ctx.createScriptProcessor(FRAME_SIZE, 1, 1)
      proc.onaudioprocess = (e) => onFrame(e.inputBuffer.getChannelData(0), ctx.sampleRate)
      source.connect(proc)
      proc.connect(ctx.destination)
      audioRef.current = { ctx, stream, proc, source }
      detectorRef.current = createSpeechDetector()
      setMicState('waiting')
    } catch {
      setMicState('error') // 마이크 권한이 없거나 마이크가 없음 → 버튼으로 계속 주문
    }
  }, [onFrame])

  const close = useCallback(() => {
    const audio = audioRef.current
    audioRef.current = null
    captureRef.current = null
    manualRef.current = null
    preRollRef.current = []
    if (audio) {
      audio.proc.onaudioprocess = null
      audio.source.disconnect()
      audio.proc.disconnect()
      audio.stream.getTracks().forEach((t) => t.stop())
      audio.ctx.close()
    }
    setMicState((s) => (s === 'error' ? s : 'off'))
  }, [])

  // 결제·응답 대기 중 등에는 말 감지를 멈춘다 (듣는 중이던 말은 끝까지 받는다)
  const setPaused = useCallback((paused) => {
    pausedRef.current = paused
  }, [])

  // 마이크 버튼: 기다리는 중이면 바로 듣기 시작, 듣는 중이면 바로 끝내고 보내기
  // 안내를 읽는 중에 누르면 안내를 바로 멈추고 듣는다
  const toggleListening = useCallback(async () => {
    if (!captureRef.current && speakingRef.current) stopSpeaking()
    if (!audioRef.current) await open()
    if (!audioRef.current) return
    if (captureRef.current) {
      finishCapture()
    } else {
      detectorRef.current.forceStart()
      beginCapture()
      manualRef.current = 0
    }
  }, [open, beginCapture, finishCapture, stopSpeaking])

  useEffect(
    () => () => {
      stopPlayback()
      close()
    },
    [close, stopPlayback],
  )

  const setSpeed = useCallback((speed) => {
    speedRef.current = speed || 'normal'
  }, [])

  return { micState, speaking, speak, stopSpeaking, open, close, setPaused, toggleListening, setSpeed }
}
