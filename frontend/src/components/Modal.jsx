// Figma 부품 `Modal`: 예외 안내 창. 제목, 문장, 버튼 2~3개
export default function Modal({ icon, title, text, actions }) {
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal__box">
        {icon && <div className="modal__icon" aria-hidden="true">{icon}</div>}
        <h2 className="modal__title">{title}</h2>
        {text && <p className="modal__text">{text}</p>}
        <div className="modal__actions">
          {actions.map(({ label, onClick, variant = 'primary' }) => (
            <button key={label} type="button" className={`btn btn--${variant}`} onClick={onClick}>
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
