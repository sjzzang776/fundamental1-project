// Figma 부품 `MicIndicator`: listening / speaking / idle / error. 누르면 말하기 시작·끝
const TEXT = {
  idle: '눌러서 말하기',
  listening: '듣고 있어요 · 다 말하면 누르세요',
  speaking: '말하는 중',
  thinking: '잠시만요',
  error: '음성이 안 돼요 · 버튼을 눌러 주세요',
}

export default function MicIndicator({ state, onPress, disabled }) {
  return (
    <button
      type="button"
      className={`mic mic--${state}`}
      onClick={onPress}
      disabled={disabled || state === 'error' || state === 'thinking'}
      aria-label={TEXT[state]}
    >
      <span className="mic__icon" aria-hidden="true">{state === 'error' ? '🔇' : '🎤'}</span>
      <span className="mic__text">{TEXT[state]}</span>
    </button>
  )
}
