import { useEffect, useMemo, useState, type RefObject } from 'react'
import type { AnimalView, StepView } from '../types'
import { colorForAppointment } from '../utils/colors'
import {
  animalNamesLine,
  formatStepDisplayTime,
  gridLocalHm,
  hmToMinutes,
  houseLocalToDisplay,
} from '../utils/time'

const HOUR_HEIGHT = 56
const CARD_H = 40
const STACK_PEEK = 5
const STACK_PEEK_MAX = 2
/** Overlap slack: treat as same cluster if cards almost touch. */
const OVERLAP_SLACK = 2

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
  const hasEarly = steps.some((s) => careMinutes(gridLocalHm(s)) < 4 * 60)
  const hasLate = steps.some((s) => careMinutes(gridLocalHm(s)) >= 19 * 60)

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

type Placed = {
  step: StepView
  top: number
  height: number
}

type Cluster = {
  id: string
  steps: StepView[]
  top: number
  height: number
}

function placeSteps(steps: StepView[], gridStartCm: number): Placed[] {
  return steps
    .map((step) => {
      const cm = careMinutes(gridLocalHm(step))
      const top = ((cm - gridStartCm) / 60) * HOUR_HEIGHT
      return { step, top, height: CARD_H }
    })
    .sort((a, b) => a.top - b.top || a.step.id - b.step.id)
}

/** Connected components by vertical overlap → stacks. */
function buildClusters(placed: Placed[]): Cluster[] {
  if (placed.length === 0) return []

  const parent = placed.map((_, i) => i)
  const find = (i: number): number => {
    if (parent[i] !== i) parent[i] = find(parent[i])
    return parent[i]
  }
  const unite = (a: number, b: number) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent[rb] = ra
  }

  const active: number[] = []
  for (let i = 0; i < placed.length; i++) {
    const item = placed[i]
    for (let j = active.length - 1; j >= 0; j--) {
      const prev = placed[active[j]]
      if (prev.top + prev.height <= item.top + OVERLAP_SLACK) {
        active.splice(j, 1)
      }
    }
    for (const j of active) unite(i, j)
    active.push(i)
  }

  const groups = new Map<number, Placed[]>()
  for (let i = 0; i < placed.length; i++) {
    const root = find(i)
    const list = groups.get(root) ?? []
    list.push(placed[i])
    groups.set(root, list)
  }

  return [...groups.values()].map((group) => {
    const sorted = [...group].sort(
      (a, b) => a.top - b.top || a.step.id - b.step.id,
    )
    const top = sorted[0].top
    const bottom = Math.max(...sorted.map((g) => g.top + g.height))
    return {
      id: sorted.map((g) => g.step.id).join('-'),
      steps: sorted.map((g) => g.step),
      top,
      height: bottom - top,
    }
  })
}

function cardMeta(
  step: StepView,
  animals: AnimalView[],
  houseTz: string,
  displayTz: string,
): string {
  const time = formatStepDisplayTime(step, houseTz, displayTz)
  const names = animalNamesLine(step.animal_ids, animals)
  return names ? `${time} · ${names}` : time
}

function statusClass(status: StepView['status']): string {
  if (status === 'done') return ' status-done'
  if (status === 'skipped') return ' status-skipped'
  if (status === 'overdue') return ' status-overdue'
  return ''
}

function StepCardBody({
  step,
  animals,
  houseTz,
  displayTz,
  badge,
}: {
  step: StepView
  animals: AnimalView[]
  houseTz: string
  displayTz: string
  badge?: string | null
}) {
  return (
    <>
      {step.status === 'done' && (
        <span className="step-card-mark" aria-label="выполнено">
          <IconCheck />
        </span>
      )}
      {step.status === 'skipped' && (
        <span className="step-card-mark" aria-label="пропущено">
          <IconSkip />
        </span>
      )}
      {step.status === 'overdue' && (
        <span className="step-card-mark mark-overdue" aria-label="просрочено">
          <IconOverdue />
        </span>
      )}
      {badge ? <span className="step-card-badge">{badge}</span> : null}
      <div className="title">{step.title}</div>
      <div className="meta">{cardMeta(step, animals, houseTz, displayTz)}</div>
    </>
  )
}

export function DayGrid({
  steps,
  animals,
  houseTz,
  displayTz,
  onOpenStep,
  scrollRef,
  /** Моки: фиксированное «сейчас» дома. Без пропа — живые часы по houseTz. */
  nowHouseLocal,
}: {
  steps: StepView[]
  animals: AnimalView[]
  houseTz: string
  displayTz: string
  onOpenStep: (stepId: number) => void
  scrollRef?: RefObject<HTMLDivElement | null>
  nowHouseLocal?: string
}) {
  const bands = buildBands(steps)
  const gridStartCm = bands[0]?.startCm ?? 4 * 60
  const gridEndCm = bands.at(-1)?.endCm ?? 19 * 60
  const clusters = useMemo(
    () => buildClusters(placeSteps(steps, gridStartCm)),
    [steps, gridStartCm],
  )
  const totalHeight = ((gridEndCm - gridStartCm) / 60) * HOUR_HEIGHT

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const expanded = clusters.find((c) => c.id === expandedId) ?? null

  useEffect(() => {
    setExpandedId(null)
  }, [steps])

  const [liveHm, setLiveHm] = useState(() => houseNowHm(houseTz))
  useEffect(() => {
    if (nowHouseLocal != null) return
    const tick = () => setLiveHm(houseNowHm(houseTz))
    tick()
    const id = window.setInterval(tick, 30_000)
    return () => window.clearInterval(id)
  }, [houseTz, nowHouseLocal])

  useEffect(() => {
    if (!expandedId) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpandedId(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expandedId])

  const nowHm = nowHouseLocal ?? liveHm
  const nowCm = careMinutes(nowHm)
  const nowVisible = nowCm >= gridStartCm && nowCm <= gridEndCm
  const nowTop = ((nowCm - gridStartCm) / 60) * HOUR_HEIGHT

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

      {nowVisible && (
        <div className="now-line" style={{ top: nowTop }} aria-hidden="true">
          <span className="now-line-dot" />
          <span className="now-line-rule" />
        </div>
      )}

      <div className="cards-layer" style={{ height: totalHeight }}>
        {clusters.map((cluster) => {
          const topStep = cluster.steps[0]
          const isStack = cluster.steps.length > 1
          const hidden = cluster.steps.length - 1
          const peekCount = isStack
            ? Math.min(STACK_PEEK_MAX, cluster.steps.length - 1)
            : 0
          const color = colorForAppointment(topStep.appointment_id)
          const dimmed = expandedId != null && expandedId !== cluster.id

          return (
            <div
              key={cluster.id}
              className={`step-stack${dimmed ? ' dimmed' : ''}`}
              style={{
                top: cluster.top,
                height: CARD_H + peekCount * STACK_PEEK,
                left: 4,
                right: 4,
              }}
            >
              {Array.from({ length: peekCount }, (_, i) => {
                const depth = peekCount - i
                const peekStep =
                  cluster.steps[
                    Math.min(depth, cluster.steps.length - 1)
                  ]
                return (
                  <div
                    key={`peek-${depth}`}
                    className="step-card step-card-peek"
                    style={{
                      top: depth * STACK_PEEK,
                      height: CARD_H,
                      left: depth * 3,
                      right: depth * 3,
                      background: colorForAppointment(peekStep.appointment_id),
                      zIndex: peekCount - depth + 1,
                    }}
                    aria-hidden="true"
                  />
                )
              })}
              <button
                type="button"
                className={`step-card step-card-front${statusClass(topStep.status)}`}
                style={{
                  top: 0,
                  height: CARD_H,
                  left: 0,
                  right: 0,
                  background: color,
                  zIndex: peekCount + 1,
                }}
                onClick={() => {
                  if (isStack) setExpandedId(cluster.id)
                  else onOpenStep(topStep.id)
                }}
              >
                <StepCardBody
                  step={topStep}
                  animals={animals}
                  houseTz={houseTz}
                  displayTz={displayTz}
                  badge={hidden > 0 ? `+${hidden}` : null}
                />
              </button>
            </div>
          )
        })}
      </div>

      {expanded && (
        <div
          className="stack-expand-overlay"
          role="presentation"
          onClick={() => setExpandedId(null)}
        >
          <div
            className="stack-expand-panel"
            role="dialog"
            aria-label="Назначения в это время"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="stack-expand-header">
              <span>{appointmentsCountLabel(expanded.steps.length)}</span>
              <button
                type="button"
                className="stack-expand-close"
                onClick={() => setExpandedId(null)}
              >
                Свернуть
              </button>
            </div>
            <div className="stack-expand-list">
              {expanded.steps.map((step) => (
                <button
                  key={step.id}
                  type="button"
                  className={`step-card step-card-expanded${statusClass(step.status)}`}
                  style={{
                    background: colorForAppointment(step.appointment_id),
                  }}
                  onClick={() => {
                    setExpandedId(null)
                    onOpenStep(step.id)
                  }}
                >
                  <StepCardBody
                    step={step}
                    animals={animals}
                    houseTz={houseTz}
                    displayTz={displayTz}
                  />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/** Pixel offset so «сейчас» не у самого края viewport. */
const NOW_SCROLL_OFFSET = 96

function houseNowHm(houseTz: string): string {
  return new Date().toLocaleTimeString('en-GB', {
    timeZone: houseTz,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function appointmentsCountLabel(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} назначение`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
    return `${n} назначения`
  }
  return `${n} назначений`
}

function IconCheck() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path
        d="M3.2 8.2 L6.6 11.5 L12.8 4.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconSkip() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path
        d="M3.5 8 H12.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function IconOverdue() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <circle cx="8" cy="8" r="3.2" fill="currentColor" />
    </svg>
  )
}

/** Scroll so линия текущего времени около верха (с отступом). Вне сетки — clamp. */
export function scrollTopForNow(
  steps: StepView[],
  houseTz: string,
  nowHouseLocal?: string,
  offsetPx: number = NOW_SCROLL_OFFSET,
): number {
  const bands = buildBands(steps)
  const gridStartCm = bands[0]?.startCm ?? 4 * 60
  const gridEndCm = bands.at(-1)?.endCm ?? 19 * 60
  const hm = nowHouseLocal ?? houseNowHm(houseTz)
  let nowCm = careMinutes(hm)
  if (nowCm < gridStartCm) nowCm = gridStartCm
  if (nowCm > gridEndCm) nowCm = gridEndCm
  const nowTop = ((nowCm - gridStartCm) / 60) * HOUR_HEIGHT
  return Math.max(0, nowTop - offsetPx)
}

/** @deprecated предпочтительно scrollTopForNow */
export function scrollTopForEight(steps: StepView[]): number {
  const bands = buildBands(steps)
  const gridStartCm = bands[0]?.startCm ?? 4 * 60
  const eightCm = 4 * 60
  return Math.max(0, ((eightCm - gridStartCm) / 60) * HOUR_HEIGHT)
}
