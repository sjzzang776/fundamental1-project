// 05a-coupon-ask / 05b-coupon-scan / e05~e08 쿠폰 실패·사용 불가·쿠폰 메뉴 없음
// 안내 문장(이유)은 서버가 reply_text 로 쉬운 말로 보내 준다.
import { useState } from 'react'
import ChoiceList from '../components/ChoiceList.jsx'
import GuideAnimation from '../components/GuideAnimation.jsx'
import { CHOICE } from '../lib/screen.js'

const ICON = {
  '쿠폰 있어요': '🎟️',
  없어요: '🙅',
  [CHOICE.NO_COUPON]: '💳',
  [CHOICE.STAFF]: '🙋',
  [CHOICE.ADD_COUPON_MENU]: '🛒',
}

export default function CouponScreen({ screen, choices, onChoose, onScan, disabled }) {
  const showGuide = screen === 'coupon-scan' || screen === 'coupon-problem'
  return (
    <div className="coupon-screen">
      {showGuide && <GuideAnimation type="barcode" />}
      <ChoiceList
        choices={choices}
        onChoose={onChoose}
        disabled={disabled}
        describe={(c) => ({ icon: ICON[c], variant: c === CHOICE.STAFF ? 'secondary' : 'primary' })}
      />
      {screen !== 'coupon-ask' && <PracticeBarcode onScan={onScan} disabled={disabled} />}
    </div>
  )
}

// 연습용: 바코드 스캐너가 없을 때 바코드 글자를 직접 넣는다 (TEST0001 ~ TEST0005)
function PracticeBarcode({ onScan, disabled }) {
  const [code, setCode] = useState('')
  const submit = (e) => {
    e.preventDefault()
    if (!code.trim()) return
    onScan(code.trim())
    setCode('')
  }
  return (
    <form className="practice" onSubmit={submit}>
      <span className="practice__tag">연습용 · 스캐너 대신</span>
      <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="바코드 (예: TEST0001)" aria-label="연습용 바코드" />
      <button type="submit" className="btn btn--secondary btn--small" disabled={disabled}>
        바코드 읽기
      </button>
    </form>
  )
}
