// 02-menu-recommend: 추천 메뉴를 큰 사진 + 큰 가격 카드로. 메뉴가 아닌 버튼([추천해 주세요] 등)은 아래에.
import { ChoiceButton } from '../components/ChoiceList.jsx'
import MenuCard from '../components/MenuCard.jsx'
import { won } from '../lib/format.js'

export default function MenuScreen({ choices, cart, catalog, onChoose, onBrowse, disabled }) {
  const menuChoices = choices.filter((c) => catalog.byName[c])
  const otherChoices = choices.filter((c) => !catalog.byName[c])
  const count = cart?.items?.reduce((sum, i) => sum + i.quantity, 0) ?? 0

  return (
    <div className="menu-screen">
      {menuChoices.length > 0 && (
        <div className="menu-grid">
          {menuChoices.map((name) => (
            <MenuCard key={name} name={name} menu={catalog.byName[name]} disabled={disabled} onClick={() => onChoose(name)} />
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
