// Figma 부품 `MenuCard`: 사진(없으면 그림 글자 자리표시), 메뉴 이름, 큰 가격
import { menuEmoji, won } from '../lib/format.js'

export default function MenuCard({ menu, name, onClick, disabled }) {
  const soldOut = menu?.sold_out
  return (
    <button type="button" className="menu-card" onClick={onClick} disabled={disabled || soldOut}>
      {menu?.image_url ? (
        <img className="menu-card__photo menu-card__photo--img" src={menu.image_url} alt="" />
      ) : (
        <span className="menu-card__photo" aria-hidden="true">{menuEmoji(menu)}</span>
      )}
      <span className="menu-card__name">{menu?.name ?? name}</span>
      {menu?.price != null && (
        <span className="menu-card__price">
          {soldOut ? '다 팔렸어요' : won(menu.price)}
          {!soldOut && menu.set_price != null && <small>세트 {won(menu.set_price)}</small>}
        </span>
      )}
    </button>
  )
}
