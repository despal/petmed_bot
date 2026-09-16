/** Time helpers for mock UI. House TZ drives schedule; display TZ only for labels. */

export function parseHm(hm: string): { h: number; m: number } {
  const [h, m] = hm.split(':').map(Number)
  return { h, m }
}

export function hmToMinutes(hm: string): number {
  const { h, m } = parseHm(hm)
  return h * 60 + m
}

export function minutesToHm(total: number): string {
  const t = ((total % (24 * 60)) + 24 * 60) % (24 * 60)
  const h = Math.floor(t / 60)
  const m = t % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** Offset of display TZ relative to house TZ, in minutes (display - house). */
export function tzOffsetDiffMinutes(
  houseTz: string,
  displayTz: string,
  at: Date = new Date(),
): number {
  const house = offsetMinutes(houseTz, at)
  const display = offsetMinutes(displayTz, at)
  return display - house
}

function offsetMinutes(iana: string, at: Date): number {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: iana,
    timeZoneName: 'shortOffset',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const parts = fmt.formatToParts(at)
  const tz = parts.find((p) => p.type === 'timeZoneName')?.value ?? 'GMT'
  const m = tz.match(/GMT([+-])(\d+)(?::(\d+))?/)
  if (!m) return 0
  const sign = m[1] === '-' ? -1 : 1
  const hours = Number(m[2])
  const mins = Number(m[3] ?? 0)
  return sign * (hours * 60 + mins)
}

/** Convert house-local HH:MM to display-local HH:MM for the same absolute moment. */
export function houseLocalToDisplay(
  houseLocalHm: string,
  houseTz: string,
  displayTz: string,
  at: Date = new Date(),
): string {
  if (houseTz === displayTz) return houseLocalHm
  const diff = tzOffsetDiffMinutes(houseTz, displayTz, at)
  return minutesToHm(hmToMinutes(houseLocalHm) + diff)
}

export function formatStepTime(
  plannedLocal: string,
  accuracy: 'exact' | 'inexact',
  houseTz: string,
  displayTz: string,
): string {
  const shown = houseLocalToDisplay(plannedLocal, houseTz, displayTz)
  return accuracy === 'inexact' ? `~ ${shown}` : shown
}

/** HH:MM on the schedule grid: fact for done, planned otherwise. */
export function gridLocalHm(step: {
  status: string
  planned_local: string
  fact_local: string | null
}): string {
  if (step.status === 'done' && step.fact_local) return step.fact_local
  return step.planned_local
}

/** Card/modal label: fact time (exact) for done, planned slot otherwise. */
export function formatStepDisplayTime(
  step: {
    status: string
    planned_local: string
    fact_local: string | null
    time_accuracy: 'exact' | 'inexact'
  },
  houseTz: string,
  displayTz: string,
): string {
  if (step.status === 'done' && step.fact_local) {
    return houseLocalToDisplay(step.fact_local, houseTz, displayTz)
  }
  return formatStepTime(step.planned_local, step.time_accuracy, houseTz, displayTz)
}

export function animalNamesLine(
  animalIds: number[],
  animals: { id: number; name: string }[],
): string {
  const names = animalIds
    .map((id) => animals.find((a) => a.id === id)?.name)
    .filter(Boolean) as string[]
  if (names.length === 0) return ''
  if (names.length === 1) return names[0]
  if (names.length === 2) return `${names[0]}, ${names[1]}`
  return `${names[0]} и ещё ${names.length - 1}`
}

export function isFutureHouseTime(
  chosenHm: string,
  nowHouseLocal: string,
): boolean {
  return hmToMinutes(chosenHm) > hmToMinutes(nowHouseLocal)
}
