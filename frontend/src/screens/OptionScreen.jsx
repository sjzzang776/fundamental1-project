// 03a-option-set / 03b-option-drink / 03c-option-size: 한 번에 하나씩 묻는다.
// 음료는 5개라서 3개 + [다른 음료 보기] → 2개 + [앞으로] 로 나눠 보여 준다.
import ChoiceList from '../components/ChoiceList.jsx'

const ICON = {
  세트: '🍔🍟🥤',
  단품: '🍔',
  미디엄: '🥤',
  라지: '🥤🥤',
  코카콜라: '🥤',
  '코카콜라 제로': '🥤',
  스프라이트: '🥤',
  아메리카노: '☕',
  '오렌지 주스': '🍊',
}

export default function OptionScreen({ screen, choices, optionPrice, onChoose, disabled }) {
  const describe = (c) => {
    const extra = optionPrice[c]
    const sub = c === '세트' ? '감자튀김 + 음료' : extra > 0 ? `+${extra.toLocaleString('ko-KR')}원` : undefined
    return { icon: ICON[c], sub }
  }
  return (
    <div className={`option-screen option-screen--${screen}`}>
      <ChoiceList
        choices={choices}
        onChoose={onChoose}
        disabled={disabled}
        describe={describe}
        moreLabel={screen === 'option-drink' ? '다른 음료 보기' : '다른 것 보기'}
      />
    </div>
  )
}
