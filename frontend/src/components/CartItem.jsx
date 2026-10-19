// Figma 부품 `CartItem`: 이름, 수량, 가격, [빼기] [하나 더]
// side 가 있으면(세트) "사이드: 후렌치 후라이 [바꾸기]" 줄을 보여 준다 (기획 결정 2026-10-19 · 이슈 #13)
import { won } from '../lib/format.js'

export default function CartItem({ item, onChange, side, onSide, disabled }) {
  return (
    <li className="cart-item">
      <div className="cart-item__info">
        <span className="cart-item__name">{item.label}</span>
        <span className="cart-item__price">
          {item.quantity}개 · <b>{won(item.line_total)}</b>
        </span>
      </div>
      {side && onSide && (
        <div className="cart-item__side">
          <span>
            사이드: <b>{side.name}</b>
          </span>
          <button type="button" className="btn btn--secondary btn--small" disabled={disabled} onClick={() => onSide(item, side)}>
            🔄 바꾸기
          </button>
        </div>
      )}
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
