// Figma 부품 `MicIndicator`: listening / speaking / idle / error.
// 주문 중에는 말하면 바로 듣는다(handsFree). 버튼을 눌러 직접 시작·끝낼 수도 있다.
const TEXT = {
  idle: '눌러서 말하기',
  listening: '듣고 있어요 · 말을 멈추면 바로 보내요',
  speaking: '말하는 중 · 말씀하시면 멈춰요',
  thinking: '잠시만요',
  error: '음성이 안 돼요 · 버튼을 눌러 주세요',
}
const HANDS_FREE_IDLE = '말씀하시면 바로 들어요'

export default function MicIndicator({ state, onPress, disabled, handsFree = false }) {
  const text = state === 'idle' && handsFree ? HANDS_FREE_IDLE : TEXT[state]
  return (
    <button
      type="button"
      className={`mic mic--${state}`}
      onClick={onPress}
      disabled={disabled || state === 'error' || state === 'thinking'}
      aria-label={text}
    >
      <span className="mic__icon" aria-hidden="true">{state === 'error' ? '🔇' : '🎤'}</span>
      <span className="mic__text">{text}</span>
    </button>
  )
}
