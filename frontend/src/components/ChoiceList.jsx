// Figma 부품 `ChoiceButton` 목록. 5개 이상이면 쪽을 나눈다 (한 화면 최대 4개).
import { useEffect, useState } from 'react'
import { paginate } from '../lib/paginate.js'

export function ChoiceButton({ icon, label, sub, onClick, disabled, variant = 'primary' }) {
  return (
    <button type="button" className={`choice choice--${variant}`} onClick={onClick} disabled={disabled}>
      {icon && <span className="choice__icon" aria-hidden="true">{icon}</span>}
      <span className="choice__label">{label}</span>
      {sub && <span className="choice__sub">{sub}</span>}
    </button>
  )
}

export default function ChoiceList({
  choices,
  onChoose,
  disabled,
  describe = () => ({}),
  moreLabel = '다른 것 보기',
  backLabel = '앞으로',
}) {
  const pages = paginate(choices)
  const [page, setPage] = useState(0)
  useEffect(() => setPage(0), [choices.join('|')])

  if (!choices.length) return null
  const current = pages[Math.min(page, pages.length - 1)]
  const last = page >= pages.length - 1

  return (
    <div className="choice-list">
      {current.map((c) => {
        const { icon, sub, variant } = describe(c)
        return (
          <ChoiceButton key={c} icon={icon} label={c} sub={sub} variant={variant} disabled={disabled} onClick={() => onChoose(c)} />
        )
      })}
      {pages.length > 1 && (
        <ChoiceButton
          variant="secondary"
          icon={last ? '◀' : '▶'}
          label={last ? backLabel : moreLabel}
          sub={`${page + 1} / ${pages.length}쪽`}
          onClick={() => setPage(last ? 0 : page + 1)}
        />
      )}
    </div>
  )
}
