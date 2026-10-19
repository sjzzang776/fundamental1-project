// Figma 부품 `ChoiceButton` 목록. 5개 이상이면 쪽을 나눈다 (한 화면 최대 4개).
// 말로도 쪽을 넘긴다: 서버 응답 actions 의 UI 명령("다른 음료 보여 줘" → next_page)을 ScreenCommand 로 받는다.
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { paginate } from '../lib/paginate.js'

// { command: 'next_page' | 'prev_page' | 'show_menu' | 'close_menu', category, seq } (Kiosk 가 넣어 줌)
export const ScreenCommand = createContext(null)

export function nextPage(page, count, command) {
  if (command === 'next_page') return page >= count - 1 ? 0 : page + 1 // 버튼과 같이 마지막 쪽 다음은 첫 쪽
  if (command === 'prev_page') return Math.max(page - 1, 0)
  return page
}

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
  const cmd = useContext(ScreenCommand)
  const seenRef = useRef(cmd?.seq) // 새로 그려질 때 예전 명령을 다시 따르지 않게
  useEffect(() => {
    if (!cmd || cmd.seq === seenRef.current) return
    seenRef.current = cmd.seq
    setPage((p) => nextPage(p, pages.length, cmd.command))
  }, [cmd?.seq]) // eslint-disable-line react-hooks/exhaustive-deps

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
