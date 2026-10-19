// Figma 부품 `CartItem`: 이름, 수량, 가격, [빼기] [하나 더]
import { won } from '../lib/format.js'

export default function CartItem({ item, onChange, disabled }) {
  return (
    <li className="cart-item">
      <div className="cart-item__info">
        <span className="cart-item__name">{item.label}</span>
        <span className="cart-item__price">
          {item.quantity}개 · <b>{won(item.line_total)}</b>
        </span>
      </div>
      {onChange && (
        <div className="cart-item__actions">
          <button type="button" className="btn btn--secondary btn--small" disabled={disabled} onClick={() => onChange(item, -1)}>
            − 빼기
          </button>
          <button type="button" className="btn btn--secondary btn--small" disabled={disabled} onClick={() => onChange(item, 1)}>
            ＋ 하나 더
          </button>
        </div>
      )}
    </li>
  )
}
