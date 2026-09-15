import type { RefObject } from 'react'
import type { AnimalView, StepView } from '../types'
import { colorForAppointment } from '../utils/colors'
import {
  animalNamesLine,
  formatStepTime,
  hmToMinutes,
  houseLocalToDisplay,
} from '../utils/time'

const HOUR_HEIGHT = 56
const CARD_H = 52

/** Minutes from care-day start 04:00. */
function careMinutes(hm: string): number {
  const m = hmToMinutes(hm)
  return m >= 4 * 60 ? m - 4 * 60 : m + 20 * 60
}

function hmFromCareMinutes(cm: number): string {
  const m = (cm + 4 * 60) % (24 * 60)
  const h = Math.floor(m / 60)
  const min = m % 60
  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`
}

type Band = {
  key: string
  kind: 'edge' | 'morning' | 'day' | 'evening'
  label: string | null
  startCm: number
  endCm: number
}

function buildBands(steps: StepView[]): Band[] {
  const hasEarly = steps.some((s) => careMinutes(s.planned_local) < 4 * 60)
  const hasLate = steps.some((s) => careMinutes(s.planned_local) >= 19 * 60)

  const bands: Band[] = []
  if (hasEarly) {
    bands.push({
      key: 'early',
      kind: 'edge',
      label: null,
      startCm: 0,
      endCm: 4 * 60,
    })
  }
  bands.push(
    {
      key: 'morning',
      kind: 'morning',
      label: 'Утро',
      startCm: 4 * 60,
      endCm: 9 * 60,
    },
    {
      key: 'day',
      kind: 'day',
      label: 'День',
      startCm: 9 * 60,
      endCm: 14 * 60,
    },
    {
      key: 'evening',
      kind: 'evening',
      label: 'Вечер',
      startCm: 14 * 60,
      endCm: 19 * 60,
    },
  )
  if (hasLate) {
    bands.push({
      key: 'late',
      kind: 'edge',
      label: null,
      startCm: 19 * 60,
      endCm: 24 * 60,
    })
  }
  return bands
}

type LaidOut = {
  step: StepView
  top: number
  height: number
  col: number
  cols: number
}

function layoutCards(steps: StepView[], gridStartCm: number): LaidOut[] {
  const items: LaidOut[] = steps
    .map((step) => {
      const cm = careMinutes(step.planned_local)
      const top = ((cm - gridStartCm) / 60) * HOUR_HEIGHT
      return { step, top, height: CARD_H, col: 0, cols: 1 }
    })
    .sort((a, b) => a.top - b.top || a.step.id - b.step.id)

  const active: LaidOut[] = []
  for (const item of items) {
    for (let i = active.length - 1; i >= 0; i--) {
      if (active[i].top + active[i].height <= item.top + 2) active.splice(i, 1)
    }
    const used = new Set(active.map((a) => a.col))
    let col = 0
    while (used.has(col) && col < 2) col++
    item.col = col
    active.push(item)
    const groupCols = Math.min(3, Math.max(...active.map((a) => a.col)) + 1)
    for (const a of active) a.cols = groupCols
    item.cols = groupCols
  }
  return items
}

export function DayGrid({
  steps,
  animals,
  houseTz,
  displayTz,
  onOpenStep,
  scrollRef,
}: {
  steps: StepView[]
  animals: AnimalView[]
  houseTz: string
  displayTz: string
  onOpenStep: (stepId: number) => void
  scrollRef?: RefObject<HTMLDivElement | null>
}) {
  const bands = buildBands(steps)
  const gridStartCm = bands[0]?.startCm ?? 4 * 60
  const gridEndCm = bands.at(-1)?.endCm ?? 19 * 60
  const laid = layoutCards(steps, gridStartCm)
  const totalHeight = ((gridEndCm - gridStartCm) / 60) * HOUR_HEIGHT

  return (
    <div className="day-grid" ref={scrollRef} style={{ height: totalHeight }}>
      {bands.map((band) => {
        const top = ((band.startCm - gridStartCm) / 60) * HOUR_HEIGHT
        const height = ((band.endCm - band.startCm) / 60) * HOUR_HEIGHT
        return (
          <div
            key={band.key}
            className={`slot-band ${band.kind}`}
            style={{
              position: 'absolute',
              top,
              left: 0,
              right: 0,
              height,
            }}
          >
            {band.label && <div className="slot-label">{band.label}</div>}
          </div>
        )
      })}

      {Array.from(
        { length: (gridEndCm - gridStartCm) / 60 },
        (_, i) => gridStartCm + i * 60,
      ).map((cm) => {
        const houseHm = hmFromCareMinutes(cm)
        const label = houseLocalToDisplay(houseHm, houseTz, displayTz)
        const top = ((cm - gridStartCm) / 60) * HOUR_HEIGHT
        return (
          <div
            key={cm}
            className="hour-row"
            style={{
              position: 'absolute',
              top,
              left: 0,
              right: 0,
              height: HOUR_HEIGHT,
            }}
          >
            <div className="hour-label">{label}</div>
            <div className="hour-track" />
          </div>
        )
      })}

      <div className="cards-layer" style={{ height: totalHeight }}>
        {laid.map(({ step, top, height, col, cols }) => {
          const widthPct = 100 / cols
          const color = colorForAppointment(step.appointment_id)
          const closed = step.status === 'done' || step.status === 'skipped'
          const time = formatStepTime(
            step.planned_local,
            step.time_accuracy,
            houseTz,
            displayTz,
          )
          const names = animalNamesLine(step.animal_ids, animals)
          const narrow = cols >= 3
          return (
            <button
              key={step.id}
              type="button"
              className={`step-card${closed ? ' closed' : ''}`}
              style={{
                top,
                height,
                left: `calc(${col * widthPct}% + 4px)`,
                width: `calc(${widthPct}% - 8px)`,
                background: color,
              }}
              onClick={() => onOpenStep(step.id)}
            >
              <div className="title">{step.title}</div>
              <div className="meta">{time}</div>
              {!narrow && names && <div className="meta">{names}</div>}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** Pixel offset to scroll so 08:00 is near the top. */
export function scrollTopForEight(steps: StepView[]): number {
  const bands = buildBands(steps)
  const gridStartCm = bands[0]?.startCm ?? 4 * 60
  const eightCm = 4 * 60
  return Math.max(0, ((eightCm - gridStartCm) / 60) * HOUR_HEIGHT)
}
