/** HTTP client for petmed API. Auth: Authorization: tma <initData> */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || ''

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

function initData(): string {
  const tg = (window as unknown as { Telegram?: { WebApp?: { initData?: string } } })
    .Telegram?.WebApp
  if (tg?.initData) return tg.initData
  // Local live-dev without Telegram: empty — server must use DEV_TELEGRAM_ID
  return ''
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const data = initData()
  if (data) headers.set('Authorization', `tma ${data}`)

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg ?? d).join('; ')
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, String(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  me: () => request<{ user: UserDto; house: HouseDto | null }>('/api/me'),
  createHouse: (schedule_timezone: string) =>
    request<{ user: UserDto; house: HouseDto }>('/api/house', {
      method: 'POST',
      body: JSON.stringify({ schedule_timezone }),
    }),
  careDay: () => request<CareDayDto>('/api/care-day'),
  appointments: () => request<AppointmentDto[]>('/api/appointments'),
  mark: (stepId: number, kind: string, local_time?: string) =>
    request(`/api/steps/${stepId}/mark`, {
      method: 'POST',
      body: JSON.stringify({ kind, local_time }),
    }),
  addAnimal: (name: string, avatar_key?: string | null) =>
    request('/api/animals', {
      method: 'POST',
      body: JSON.stringify({ name, avatar_key }),
    }),
  patchAnimal: (id: number, body: { name?: string; avatar_key?: string | null }) =>
    request(`/api/animals/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  createAppointment: (body: Record<string, unknown>) =>
    request('/api/appointments', { method: 'POST', body: JSON.stringify(body) }),
  patchAppointment: (id: number, body: Record<string, unknown>) =>
    request(`/api/appointments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  archiveAppointment: (id: number) =>
    request(`/api/appointments/${id}/archive`, { method: 'POST' }),
  setHouseTz: (schedule_timezone: string) =>
    request<HouseDto>('/api/house/timezone', {
      method: 'PATCH',
      body: JSON.stringify({ schedule_timezone }),
    }),
  setMyTz: (display_timezone: string) =>
    request<UserDto>('/api/me/timezone', {
      method: 'PATCH',
      body: JSON.stringify({ display_timezone }),
    }),
}

export interface UserDto {
  id: number
  display_timezone: string
  telegram_id: string | null
}

export interface HouseDto {
  id: number
  creator_user_id: number
  schedule_timezone: string
  doubler_user_id: number | null
}

export interface AnimalDto {
  id: number
  house_id: number
  name: string
  archived: boolean
  avatar_key: string | null
}

export interface AppointmentDto {
  id: number
  house_id: number
  title: string
  kind: 'fixed' | 'window' | 'relative'
  animal_ids: number[]
  archived: boolean
  silent: boolean
  course_days: number | null
  course_start_plan_date: string | null
  local_time: string | null
  slot: 'morning' | 'day' | 'evening' | null
  reference_local_time: string | null
  anchor_appointment_id: number | null
  direction: 'before' | 'after' | null
  offset_minutes: number | null
}

export interface StepDto {
  id: number
  appointment_id: number
  house_id: number
  plan_date: string
  title: string
  planned_at: string
  planned_local: string
  time_accuracy: 'exact' | 'inexact'
  status: 'pending' | 'done' | 'skipped' | 'overdue'
  slot: 'morning' | 'day' | 'evening' | null
  animal_ids: number[]
  silent: boolean
  course_label: string | null
}

export interface CareDayDto {
  id: number | null
  house_id: number
  plan_date: string
  starts_at: string
  ends_at: string
  steps: StepDto[]
  animals: AnimalDto[]
}
