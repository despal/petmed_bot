import { useState } from 'react'
import type { AnimalView, StepView } from '../types'
import {
  animalNamesLine,
  formatStepTime,
} from '../utils/time'

export function StepModal({
  step,
  animals,
  houseTz,
  displayTz,
  onClose,
  onDone,
  onDoneAt,
  onSkip,
  onEdit,
  onDisable,
}: {
  step: StepView
  animals: AnimalView[]
  houseTz: string
  displayTz: string
  onClose: () => void
  onDone: () => void
  onDoneAt: () => void
  onSkip: () => void
  onEdit: () => void
  onDisable: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const closed = step.status === 'done' || step.status === 'skipped'
  const time = formatStepTime(
    step.planned_local,
    step.time_accuracy,
    houseTz,
    displayTz,
  )
  const names = step.animal_ids
    .map((id) => animals.find((a) => a.id === id)?.name)
    .filter(Boolean)
    .join(', ')

  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-top">
          <div>
            <h2>{step.title}</h2>
            <div className="muted">{time}</div>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <div className="menu">
              <button
                type="button"
                className="icon-btn"
                aria-label="Меню"
                onClick={() => setMenuOpen((v) => !v)}
              >
                ⋯
              </button>
              {menuOpen && (
                <div className="menu-pop">
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false)
                      onEdit()
                    }}
                  >
                    Изменить
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false)
                      onDisable()
                    }}
                  >
                    Выключить
                  </button>
                </div>
              )}
            </div>
            <button type="button" className="icon-btn" onClick={onClose}>
              ×
            </button>
          </div>
        </div>

        <p style={{ margin: '0 0 8px' }}>{names || animalNamesLine(step.animal_ids, animals)}</p>
        {step.course_label && (
          <p className="muted" style={{ marginTop: 0 }}>
            {step.course_label}
          </p>
        )}
        <p className="muted">
          Статус: {statusRu(step.status)}
          {step.silent ? ' · без напоминаний' : ''}
        </p>

        {!closed && (
          <div className="btn-row">
            <button type="button" className="btn primary" onClick={onDone}>
              Выполнено
            </button>
            <button type="button" className="btn" onClick={onDoneAt}>
              Выполнено в…
            </button>
            <button type="button" className="btn" onClick={onSkip}>
              Пропустили
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function statusRu(s: StepView['status']): string {
  switch (s) {
    case 'pending':
      return 'ожидает'
    case 'done':
      return 'выполнено'
    case 'skipped':
      return 'пропущено'
    case 'overdue':
      return 'просрочено'
  }
}
