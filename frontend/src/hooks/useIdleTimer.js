// 무응답 처리 (기획서 5-2): 15초 동안 아무 반응이 없으면 "도움이 필요하세요?",
// 그 뒤 15초가 더 지나면 onTimeout. 화면을 누르거나 새 응답(resetKey)이 오면 처음부터 다시 센다.
import { useEffect, useRef, useState } from 'react'

export const WARN_MS = 15000
export const TIMEOUT_MS = 15000

export function useIdleTimer({ enabled, resetKey, onTimeout }) {
  const [warned, setWarned] = useState(false)
  const onTimeoutRef = useRef(onTimeout)
  onTimeoutRef.current = onTimeout

  useEffect(() => {
    setWarned(false)
    if (!enabled) return undefined
    let warnTimer
    let endTimer
    const arm = () => {
      clearTimeout(warnTimer)
      clearTimeout(endTimer)
      setWarned(false)
      warnTimer = setTimeout(() => {
        setWarned(true)
        endTimer = setTimeout(() => onTimeoutRef.current(), TIMEOUT_MS)
      }, WARN_MS)
    }
    arm()
    window.addEventListener('pointerdown', arm)
    window.addEventListener('keydown', arm)
    return () => {
      clearTimeout(warnTimer)
      clearTimeout(endTimer)
      window.removeEventListener('pointerdown', arm)
      window.removeEventListener('keydown', arm)
    }
  }, [enabled, resetKey])

  return warned
}
