// 04-order-confirm: 장바구니를 큰 글씨로. 항목마다 [빼기] [하나 더], 합계는 서버가 계산한 값
// 세트는 "사이드: 후렌치 후라이 [바꾸기]" → 사이드 3개 중 하나를 골라 바꾼다 (이슈 #13)
import { useState } from 'react'
import CartItem from '../components/CartItem.jsx'
import ChoiceList from '../components/ChoiceList.jsx'
import Modal from '../components/Modal.jsx'
import { won } from '../lib/format.js'
import { sideOf } from '../lib/screen.js'

const SIDE_ICON = { '후렌치 후라이': '🍟', '맥너겟 4조각': '🍗', '치즈스틱 2조각': '🧀' }

export default function ConfirmScreen({ cart, choices, sides = [], onChoose, onChangeQuantity, onChangeSide, disabled }) {
  const [picking, setPicking] = useState(null) // { item, side }
  const sideNames = sides.map((s) => s.name)

  return (
    <div className="confirm-screen">
      <ul className="cart-list">
        {cart.items.map((item) => (
          <CartItem
            key={item.item_id}
            item={item}
            side={sides.length ? sideOf(item, sideNames) : null}
            onSide={(it, side) => setPicking({ item: it, side })}
            onChange={onChangeQuantity}
            disabled={disabled}
          />
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

      {picking && (
        <Modal
          icon="🍟"
          title="사이드를 골라 주세요"
          text={`${picking.item.label} · 지금: ${picking.side.name}`}
          actions={[
            ...sides.map((s) => ({
              label: `${SIDE_ICON[s.name] ?? ''} ${s.name}${s.extra_price > 0 ? ` (+${won(s.extra_price)})` : ''}`.trim(),
              variant: s.name === picking.side.name ? 'secondary' : 'primary',
              onClick: async () => {
                const { item, side } = picking
                setPicking(null)
                if (s.name !== side.name) await onChangeSide(item, side, s)
              },
            })),
            { label: '그대로 둘게요', variant: 'secondary', onClick: () => setPicking(null) },
          ]}
        />
      )}
    </div>
  )
}

