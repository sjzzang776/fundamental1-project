// 03a-option-set / 03b-option-drink / 03c-option-size: 한 번에 하나씩 묻는다.
// 음료는 5개라서 3개 + [다른 음료 보기] → 2개 + [처음 음료] 로 나눠 보여 준다 (기획 결정 2026-10-19).
// 추가 금액은 서버 choice_items 의 extra_price 를 먼저 쓴다.
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
  '후렌치 후라이': '🍟',
  '맥너겟 4조각': '🍗',
  '치즈스틱 2조각': '🧀',
}

export default function OptionScreen({ screen, choices, optionPrice, info, onChoose, disabled }) {
  const describe = (c) => {
    const extra = info(c).extra_price ?? optionPrice[c]
    const sub = c === '세트' ? '감자튀김 + 음료' : extra > 0 ? `+${extra.toLocaleString('ko-KR')}원` : undefined
    return { icon: ICON[c], sub }
  }
  const drink = screen === 'option-drink'
  return (
    <div className={`option-screen option-screen--${screen}`}>
      <ChoiceList
        choices={choices}
        onChoose={onChoose}
        disabled={disabled}
        describe={describe}
        moreLabel={drink ? '다른 음료 보기' : '다른 것 보기'}
        backLabel={drink ? '처음 음료' : '앞으로'}
      />
    </div>
  )
}
