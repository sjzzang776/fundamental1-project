// 00-idle: 대기 화면. 아주 큰 [주문 시작] 버튼 하나
export default function IdleScreen({ onStart, busy }) {
  return (
    <main className="idle">
      <div className="idle__logo" aria-hidden="true">🍔</div>
      <h1 className="idle__store">시연 매장</h1>
      <p className="idle__hello">
        안녕하세요!
        <br />
        말씀하시거나 화면의 버튼을 눌러 주문해 주세요.
      </p>
      <button type="button" className="idle__start" onClick={onStart} disabled={busy}>
        {busy ? '잠시만요…' : '주문 시작'}
      </button>
      <p className="idle__hint">🎤 말로도 주문할 수 있어요</p>
    </main>
  )
}
