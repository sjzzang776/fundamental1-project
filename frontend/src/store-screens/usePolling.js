// 매장 화면은 3초마다 서버에서 새로 읽는다
import { useCallback, useEffect, useRef, useState } from 'react'

export const POLL_MS = 3000

export function usePolling(load, ms = POLL_MS) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  const loadRef = useRef(load)
  loadRef.current = load

  const reload = useCallback(async () => {
    try {
      setData(await loadRef.current())
      setError(false)
    } catch {
      setError(true)
    }
  }, [])

  useEffect(() => {
    reload()
    const t = setInterval(reload, ms)
    return () => clearInterval(t)
  }, [reload, ms])

  return { data, error, reload }
}
