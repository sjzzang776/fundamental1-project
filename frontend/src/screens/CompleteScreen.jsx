// 07-order-complete: 주문번호를 화면에서 가장 크게. 10초 뒤 처음 화면으로 돌아간다.
import { useEffect, useState } from 'react'
import Button from '../components/Button.jsx'

export const COMPLETE_RETURN_SEC = 10

export default function CompleteScreen({ order, onHome }) {
  const [left, setLeft] = useState(COMPLETE_RETURN_SEC)
  useEffect(() => {
    if (left <= 0) {
      onHome()
      return undefined
    }
    const t = setTimeout(() => setLeft(left - 1), 1000)
    return () => clearTimeout(t)
  }, [left, onHome])

  return (
    <div className="complete-screen">
      <p className="complete-screen__label">주문번호</p>
      <p className="complete-screen__number">{order?.order_number ?? '-'}</p>
      <p className="complete-screen__guide">🧾 번호표를 받아 가세요</p>
      <p className="complete-screen__guide">화면에 번호가 뜨면 카운터에서 받아 가세요</p>
      <Button onClick={onHome}>
        처음으로 ({left}초)
      </Button>
    </div>
  )
}
