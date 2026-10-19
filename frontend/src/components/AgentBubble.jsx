// Figma 부품 `AgentBubble`: 캐릭터 + 지금 읽어 주는 안내 문장(자막)
// state: speaking(말하는 중) / listening(듣는 중) / thinking(잠시만요)
const FACE = { speaking: '😃', listening: '👂', thinking: '🤔', idle: '🙂' }

export default function AgentBubble({ text, state = 'idle', transcript }) {
  return (
    <section className={`agent agent--${state}`} aria-live="polite">
      <span className="agent__face" aria-hidden="true">{FACE[state]}</span>
      <div className="agent__bubble">
        <p className="agent__text">{text}</p>
        {transcript && <p className="agent__heard">이렇게 들었어요: “{transcript}”</p>}
      </div>
    </section>
  )
}
