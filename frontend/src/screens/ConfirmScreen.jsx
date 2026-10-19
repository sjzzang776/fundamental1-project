// 04-order-confirm: 장바구니를 큰 글씨로. 항목마다 [빼기] [하나 더], 합계는 서버가 계산한 값
import CartItem from '../components/CartItem.jsx'
import ChoiceList from '../components/ChoiceList.jsx'
import { won } from '../lib/format.js'

export default function ConfirmScreen({ cart, choices, onChoose, onChangeQuantity, disabled }) {
  return (
    <div className="confirm-screen">
      <ul className="cart-list">
        {cart.items.map((item) => (
          <CartItem key={item.item_id} item={item} onChange={onChangeQuantity} disabled={disabled} />
        ))}
      </ul>
      <p className="cart-total">
        모두 <b>{won(cart.total_amount)}</b>
      </p>
      <ChoiceList
        choices={choices}
        onChoose={onChoose}
        disabled={disabled}
        describe={(c) => ({ icon: c === '맞아요' ? '⭕' : '✏️', variant: c === '맞아요' ? 'primary' : 'secondary' })}
      />
    </div>
  )
}
