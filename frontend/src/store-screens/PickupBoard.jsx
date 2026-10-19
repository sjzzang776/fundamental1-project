// s01-pickup-call: 가게 벽에 거는 호출 화면 (가로 1920 × 1080). 주소: /pickup
// 새로 음식이 나온 번호는 크게 깜빡이고 "123번 고객님, 음식이 나왔어요." 라고 읽어 준다.
import { useEffect, useRef, useState } from 'react'
import { storeApi } from '../api/store.js'
import KioskStage from '../screens/KioskStage.jsx'
import { usePolling } from './usePolling.js'

export default function PickupBoard() {
  const { data, error } = usePolling(storeApi.pickupBoard)
  const [soundOn, setSoundOn] = useState(false)
  const [fresh, setFresh] = useState([])
  const seenRef = useRef(null)

  useEffect(() => {
    if (!data) return
    const ready = data.ready
    if (seenRef.current) {
      const added = ready.filter((n) => !seenRef.current.includes(n))
      if (added.length) {
        setFresh(added)
        if (soundOn && window.speechSynthesis) {
          added.forEach((n) => {
            const u = new SpeechSynthesisUtterance(`${n}번 고객님, 음식이 나왔어요.`)
            u.lang = 'ko-KR'
            window.speechSynthesis.speak(u)
          })
        }
      }
    }
    seenRef.current = ready
  }, [data, soundOn])

  return (
    <KioskStage width={1920} height={1080}>
      <div className="pickup">
        <section className="pickup__col pickup__col--cooking">
          <h2>🍳 준비 중</h2>
          <ul>
            {data?.cooking.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </section>
        <section className="pickup__col pickup__col--ready">
          <h2>🔔 가져가세요</h2>
          <ul>
            {data?.ready.map((n) => (
              <li key={n} className={fresh.includes(n) ? 'pickup__fresh' : ''}>
                {n}
              </li>
            ))}
          </ul>
        </section>
        <footer className="pickup__foot">
          {error ? '⚠️ 서버와 연결이 끊겼어요' : '화면에 번호가 뜨면 카운터에서 받아 가세요'}
          {!soundOn && (
            <button type="button" className="btn btn--secondary btn--small" onClick={() => setSoundOn(true)}>
              🔊 소리 켜기
            </button>
          )}
        </footer>
      </div>
    </KioskStage>
  )
}
