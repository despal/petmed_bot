/** Forms aligned with petmed_core views (same field meaning). */

export type StandId =
  | 'no_access'
  | 'no_house'
  | 'empty_house'
  | 'full_day'
  | 'settings'

export interface UserView {
  id: number
  display_timezone: string
  telegram_id: string | null
}

export interface HouseView {
  id: number
  creator_user_id: number
  schedule_timezone: string
  doubler_user_id: number | null
}

export interface AnimalView {
  id: number
  house_id: number
  name: string
  archived: boolean
  avatar_key: string | null
}

export interface AppointmentView {
  id: number
  house_id: number
  title: string
  kind: 'fixed' | 'window' | 'relative'
  animal_ids: number[]
  archived: boolean
  silent: boolean
  course_days: number | null
  course_start_plan_date: string | null // YYYY-MM-DD
  local_time: string | null // HH:MM
  slot: 'morning' | 'day' | 'evening' | null
  reference_local_time: string | null
  anchor_appointment_id: number | null
  direction: 'before' | 'after' | null
  offset_minutes: number | null
}

export type StepStatus = 'pending' | 'done' | 'skipped' | 'overdue'
export type TimeAccuracy = 'exact' | 'inexact'


export interface StepView {
  id: number
  appointment_id: number
  house_id: number
  plan_date: string
  title: string
  planned_at: string // ISO UTC
  planned_local: string // HH:MM in house TZ
  time_accuracy: TimeAccuracy
  status: StepStatus
  slot: 'morning' | 'day' | 'evening' | null
  animal_ids: number[]
  silent: boolean
  /** Precomputed for mocks; same formula as bot course_label */
  course_label: string | null
}

export interface CareDayView {
  id: number | null
  house_id: number
  plan_date: string
  starts_at: string
  ends_at: string
  steps: StepView[]
  animals: AnimalView[]
}

export interface StandData {
  id: StandId
  label: string
  user: UserView | null
  house: HouseView | null
  careDay: CareDayView | null
  appointments: AppointmentView[]
  /** Wall-clock “now” in house local for mock UI (HH:MM) */
  nowHouseLocal: string
}

export type Overlay =
  | { type: 'step'; stepId: number }
  | { type: 'done_at'; stepId: number }
  | { type: 'animal_form'; animalId?: number }
  | { type: 'appointment_form'; appointmentId?: number; presetAnimalId?: number }
  | null

export type TabId = 'home' | `animal:${number}` | 'settings'
