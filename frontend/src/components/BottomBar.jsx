// Figma 부품 `BottomBar`: 모든 화면 아래에 고정된 [처음으로] [취소] [직원 부르기]
export default function BottomBar({ onRestart, onCancel, onStaff, disabled, staffOnly }) {
  return (
    <nav className="bottom-bar">
      {!staffOnly && (
        <>
          <button type="button" className="bottom-bar__btn" onClick={onRestart} disabled={disabled}>
            <span aria-hidden="true">↩</span> 처음으로
          </button>
          <button type="button" className="bottom-bar__btn" onClick={onCancel} disabled={disabled}>
            <span aria-hidden="true">✕</span> 취소
          </button>
        </>
      )}
      <button type="button" className="bottom-bar__btn bottom-bar__btn--staff" onClick={onStaff}>
        <span aria-hidden="true">🙋</span> 직원 부르기
      </button>
    </nav>
  )
}
