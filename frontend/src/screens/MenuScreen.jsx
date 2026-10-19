// 02-menu-recommend: 추천 메뉴를 큰 사진 + 큰 가격 카드로. 메뉴가 아닌 버튼([추천해 주세요] 등)은 아래에.
// 메뉴 정보는 서버 choice_items(menu_id·가격·사진)를 먼저 쓰고, 없으면 메뉴 목록에서 이름으로 찾는다.
import { ChoiceButton } from '../components/ChoiceList.jsx'
import MenuCard from '../components/MenuCard.jsx'
import { won } from '../lib/format.js'

export default function MenuScreen({ choices, cart, catalog, info, onChoose, onBrowse, disabled }) {
  const menuOf = (c) => {
    const item = info(c)
    if (item.menu_id == null) return catalog.byName[c]
    return { ...catalog.byName[c], ...item, id: item.menu_id, name: c }
  }
  const menuChoices = choices.filter((c) => menuOf(c))
  const otherChoices = choices.filter((c) => !menuOf(c))
  const count = cart?.items?.reduce((sum, i) => sum + i.quantity, 0) ?? 0

  return (
    <div className="menu-screen">
      {menuChoices.length > 0 && (
        <div className="menu-grid">
          {menuChoices.map((name) => (
            <MenuCard key={name} name={name} menu={menuOf(name)} disabled={disabled} onClick={() => onChoose(name)} />
          ))}
        </div>
      )}
      <div className="choice-list">
        {otherChoices.map((c) => (
          <ChoiceButton key={c} label={c} icon={c === '주문할게요' ? '✅' : '💡'} disabled={disabled} onClick={() => onChoose(c)} />
        ))}
        <ChoiceButton variant="secondary" icon="📋" label="메뉴판 보기" disabled={disabled} onClick={onBrowse} />
      </div>
      {count > 0 && (
        <p className="cart-summary">
          🛒 담은 메뉴 <b>{count}개</b> · 모두 <b>{won(cart.total_amount)}</b>
        </p>
      )}
    </div>
  )
}
