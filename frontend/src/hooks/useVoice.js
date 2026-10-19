// 음성: 녹음(최대 15초) → 서버 /voice, 안내 문장 읽어 주기.
// 음성 안내는 브라우저에 들어 있는 읽어 주기(speechSynthesis)로 확정 (PM 결정 2026-10-19). 서버 /api/tts 는 쓰지 않는다.
import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_RECORD_MS = 15000

export function useVoice({ onRecorded }) {
  const [micState, setMicState] = useState('idle') // idle | listening | error
  const [speaking, setSpeaking] = useState(false)
  const recorderRef = useRef(null)
  const stopTimerRef = useRef(null)
  const onRecordedRef = useRef(onRecorded)
  onRecordedRef.current = onRecorded

  const speak = useCallback((text) => {
    const synth = window.speechSynthesis
    if (!synth || !text) return
    synth.cancel()
    const utter = new SpeechSynthesisUtterance(text)
    utter.lang = 'ko-KR'
    utter.rate = 0.9 // 어르신이 듣기 편하게 조금 천천히
    utter.onstart = () => setSpeaking(true)
    utter.onend = () => setSpeaking(false)
    utter.onerror = () => setSpeaking(false)
    synth.speak(utter)
  }, [])

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel()
    setSpeaking(false)
  }, [])

  const stopListening = useCallback(() => {
    clearTimeout(stopTimerRef.current)
    const rec = recorderRef.current
    if (rec && rec.state === 'recording') rec.stop()
  }, [])

  const startListening = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setMicState('error')
      return
    }
    stopSpeaking()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      const chunks = []
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        setMicState('idle')
        if (chunks.length) onRecordedRef.current(new Blob(chunks, { type: rec.mimeType || 'audio/webm' }))
      }
      recorderRef.current = rec
      rec.start()
      setMicState('listening')
      stopTimerRef.current = setTimeout(() => rec.state === 'recording' && rec.stop(), MAX_RECORD_MS)
    } catch {
      setMicState('error') // 마이크 권한이 없거나 마이크가 없음 → 버튼으로 계속 주문
    }
  }, [stopSpeaking])

  useEffect(() => () => {
    clearTimeout(stopTimerRef.current)
    window.speechSynthesis?.cancel()
  }, [])

  return { micState, speaking, speak, stopSpeaking, startListening, stopListening }
}
