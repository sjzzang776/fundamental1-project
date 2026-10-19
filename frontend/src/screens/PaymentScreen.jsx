// 05c-coupon-applied + 06b-payment-insert + 06c-payment-processing + e09-payment-fail
// 결제는 PG사가 정해질 때까지 모의 결제: 카드 단말 대신 화면의 연습용 버튼으로 성공/실패를 정한다.
import ChoiceList from '../components/ChoiceList.jsx'
import GuideAnimation from '../components/GuideAnimation.jsx'
import { won } from '../lib/format.js'
import { CHOICE } from '../lib/screen.js'

export default function PaymentScreen({ cart, choices, payment, onChoose, onFinish, onCancel, disabled }) {
  if (payment?.phase === 'processing') {
    return (
      <div className="payment-screen payment-screen--processing">
        <div className="spinner" aria-hidden="true" />
        <p className="payment-screen__notice">💳 카드를 빼지 말아 주세요</p>
      </div>
    )
  }

  if (payment?.phase === 'insert') {
    return (
      <div className="payment-screen">
        <p className="amount-big">{won(payment.data.amount)}</p>
        <GuideAnimation type="card" />
        <div className="practice practice--pay">
          <span className="practice__tag">연습용 · 카드 기계 대신</span>
          <button type="button" className="btn btn--primary btn--small" onClick={() => onFinish(true)}>
            결제 성공
          </button>
          <button type="button" className="btn btn--danger btn--small" onClick={() => onFinish(false)}>
            결제 실패
          </button>
        </div>
        <button type="button" className="btn btn--secondary" onClick={onCancel}>
          결제 그만두기
        </button>
      </div>
    )
  }

  const discounted = cart.discount_amount > 0
  return (
    <div className="payment-screen">
      {discounted ? (
        <dl className="price-table">
          <dt>주문 금액</dt>
          <dd>{won(cart.subtotal)}</dd>
          <dt>쿠폰 할인 · {cart.coupon?.name}</dt>
          <dd className="price-table__discount">− {won(cart.discount_amount)}</dd>
          <dt className="price-table__total">내실 금액</dt>
          <dd className="price-table__total">{won(cart.total_amount)}</dd>
        </dl>
      ) : (
        <p className="amount-big">
          <small>내실 금액</small>
          {won(cart.total_amount)}
        </p>
      )}
      <ChoiceList
        choices={choices}
        onChoose={onChoose}
        disabled={disabled}
        describe={(c) => ({ icon: c === CHOICE.STAFF ? '🙋' : '💳', variant: c === CHOICE.STAFF ? 'secondary' : 'primary' })}
      />
    </div>
  )
}
