// Figma 부품 `ProgressBar`: 지금 몇 번째 단계인지 (숫자 + 막대)
import { PROGRESS, PROGRESS_TOTAL } from '../lib/screen.js'

export default function ProgressBar({ step }) {
  const info = PROGRESS[step]
  if (!info) return <div className="progress progress--empty" />
  return (
    <div className="progress" aria-label={`${PROGRESS_TOTAL}단계 중 ${info.index}단계`}>
      <span className="progress__text">
        <b>{info.index}</b> / {PROGRESS_TOTAL} · {info.label}
      </span>
      <div className="progress__track">
        <div className="progress__fill" style={{ width: `${(info.index / PROGRESS_TOTAL) * 100}%` }} />
      </div>
    </div>
  )
}
