// Figma 부품 `GuideAnimation`: barcode / card. 화면 아래쪽(빛나는 곳)을 가리키는 움직이는 화살표 + 기기 그림
const GUIDE = {
  barcode: { device: '📱', text: '휴대폰 바코드를 아래 빛나는 곳에 대 주세요' },
  card: { device: '💳', text: '카드를 아래 빛나는 곳에 꽂아 주세요' },
}

export default function GuideAnimation({ type }) {
  const g = GUIDE[type]
  return (
    <div className={`guide guide--${type}`}>
      <span className="guide__device" aria-hidden="true">{g.device}</span>
      <span className="guide__arrow" aria-hidden="true">⬇</span>
      <p className="guide__text">{g.text}</p>
      <div className="guide__spot" aria-hidden="true" />
    </div>
  )
}
