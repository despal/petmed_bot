import { useState } from 'react'
import type { StepView } from '../types'
import { isFutureHouseTime } from '../utils/time'

export function DoneAtScreen({
  step,
  nowHouseLocal,
  onBack,
  onConfirm,
}: {
  step: StepView
  nowHouseLocal: string
  onBack: () => void
  onConfirm: (hm: string) => void
}) {
  const preset =
    step.planned_local <= nowHouseLocal ? step.planned_local : nowHouseLocal
  const [hm, setHm] = useState(preset)
  const [error, setError] = useState<string | null>(null)

  const submit = () => {
    if (isFutureHouseTime(hm, nowHouseLocal)) {
      setError('Нельзя отметить будущим временем')
      return
    }
    onConfirm(hm)
  }

  const nightHint = Number(hm.split(':')[0]) < 4

  return (
    <div className="overlay" onClick={onBack}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-top">
          <h2>Выполнено в…</h2>
          <button type="button" className="icon-btn" onClick={onBack}>
            ×
          </button>
        </div>
        <p style={{ marginTop: 0 }}>{step.title}</p>
        <div className="field">
          <label>Время дома</label>
          <input
            type="time"
            value={hm}
            onChange={(e) => {
              setHm(e.target.value)
              setError(null)
            }}
          />
        </div>
        <p className="muted">Сейчас дома: {nowHouseLocal}</p>
        {nightHint && (
          <p className="muted">
            00:00–03:59 — хвост этих суток ухода (после вечера)
          </p>
        )}
        {error && <p className="error-text">{error}</p>}
        <div className="btn-row">
          <button type="button" className="btn" onClick={onBack}>
            Назад
          </button>
          <button type="button" className="btn primary" onClick={submit}>
            Подтвердить
          </button>
        </div>
      </div>
    </div>
  )
}
