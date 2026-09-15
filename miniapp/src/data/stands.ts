import type {
  AnimalView,
  AppointmentView,
  CareDayView,
  StandData,
  StandId,
  StepView,
} from '../types'

const HOUSE_ID = 1
const PLAN_DATE = '2026-09-15'

const animalsFull: AnimalView[] = [
  { id: 1, house_id: HOUSE_ID, name: 'Север', archived: false, avatar_key: 'img01' },
  { id: 2, house_id: HOUSE_ID, name: 'Джеки', archived: false, avatar_key: 'img02' },
  { id: 3, house_id: HOUSE_ID, name: 'Рекс', archived: false, avatar_key: 'img03' },
  { id: 4, house_id: HOUSE_ID, name: 'Мурка', archived: true, avatar_key: 'img04' },
]

const appointmentsFull: AppointmentView[] = [
  {
    id: 10,
    house_id: HOUSE_ID,
    title: 'Еда утром',
    kind: 'window',
    animal_ids: [1, 2],
    archived: false,
    silent: false,
    course_days: null,
    course_start_plan_date: null,
    local_time: null,
    slot: 'morning',
    reference_local_time: '10:30',
    anchor_appointment_id: null,
    direction: null,
    offset_minutes: null,
  },
  {
    id: 11,
    house_id: HOUSE_ID,
    title: 'Антепсин',
    kind: 'relative',
    animal_ids: [1],
    archived: false,
    silent: false,
    course_days: 14,
    course_start_plan_date: '2026-09-10',
    local_time: null,
    slot: 'morning',
    reference_local_time: null,
    anchor_appointment_id: 10,
    direction: 'before',
    offset_minutes: 120,
  },
  {
    id: 12,
    house_id: HOUSE_ID,
    title: 'Альмагель',
    kind: 'relative',
    animal_ids: [1],
    archived: false,
    silent: false,
    course_days: null,
    course_start_plan_date: null,
    local_time: null,
    slot: 'morning',
    reference_local_time: null,
    anchor_appointment_id: 10,
    direction: 'after',
    offset_minutes: 30,
  },
  {
    id: 13,
    house_id: HOUSE_ID,
    title: 'Прогулка',
    kind: 'fixed',
    animal_ids: [3],
    archived: false,
    silent: true,
    course_days: null,
    course_start_plan_date: null,
    local_time: '19:00',
    slot: null,
    reference_local_time: null,
    anchor_appointment_id: null,
    direction: null,
    offset_minutes: null,
  },
  {
    id: 14,
    house_id: HOUSE_ID,
    title: 'Старый курс',
    kind: 'window',
    animal_ids: [4],
    archived: true,
    silent: false,
    course_days: 7,
    course_start_plan_date: '2026-08-01',
    local_time: null,
    slot: 'evening',
    reference_local_time: '20:30',
    anchor_appointment_id: null,
    direction: null,
    offset_minutes: null,
  },
]

function step(
  partial: Omit<StepView, 'house_id' | 'plan_date' | 'silent' | 'course_label'> &
    Partial<Pick<StepView, 'house_id' | 'plan_date' | 'silent' | 'course_label'>>,
): StepView {
  return {
    ...partial,
    house_id: partial.house_id ?? HOUSE_ID,
    plan_date: partial.plan_date ?? PLAN_DATE,
    silent: partial.silent ?? false,
    course_label: partial.course_label ?? null,
  }
}

const stepsFull: StepView[] = [
  step({
    id: 101,
    appointment_id: 11,
    title: 'Антепсин',
    planned_at: '2026-09-15T01:30:00Z',
    planned_local: '08:30',
    time_accuracy: 'inexact',
    status: 'done',
    slot: 'morning',
    animal_ids: [1],
    course_label: 'день 6 из 14',
  }),
  step({
    id: 102,
    appointment_id: 10,
    title: 'Еда утром',
    planned_at: '2026-09-15T03:30:00Z',
    planned_local: '10:30',
    time_accuracy: 'exact',
    status: 'pending',
    slot: 'morning',
    animal_ids: [1, 2],
  }),
  step({
    id: 103,
    appointment_id: 12,
    title: 'Альмагель',
    planned_at: '2026-09-15T04:00:00Z',
    planned_local: '11:00',
    time_accuracy: 'exact',
    status: 'pending',
    slot: 'morning',
    animal_ids: [1],
  }),
  step({
    id: 104,
    appointment_id: 13,
    title: 'Прогулка',
    planned_at: '2026-09-15T12:00:00Z',
    planned_local: '19:00',
    time_accuracy: 'exact',
    status: 'pending',
    slot: null,
    animal_ids: [3],
    silent: true,
  }),
  // Close times to exercise narrow columns
  step({
    id: 105,
    appointment_id: 10,
    title: 'Еда утром (повтор мок)',
    planned_at: '2026-09-15T08:30:00Z',
    planned_local: '15:30',
    time_accuracy: 'inexact',
    status: 'overdue',
    slot: 'day',
    animal_ids: [1, 2],
  }),
  step({
    id: 106,
    appointment_id: 12,
    title: 'Альмагель день',
    planned_at: '2026-09-15T08:35:00Z',
    planned_local: '15:35',
    time_accuracy: 'inexact',
    status: 'skipped',
    slot: 'day',
    animal_ids: [1],
  }),
]

const careDayFull: CareDayView = {
  id: 1,
  house_id: HOUSE_ID,
  plan_date: PLAN_DATE,
  starts_at: '2026-09-14T21:00:00Z',
  ends_at: '2026-09-15T21:00:00Z',
  steps: stepsFull,
  animals: animalsFull,
}

const userBangkok = {
  id: 1,
  display_timezone: 'Europe/Moscow',
  telegram_id: '10001',
}

const houseBangkok = {
  id: HOUSE_ID,
  creator_user_id: 1,
  schedule_timezone: 'Asia/Bangkok',
  doubler_user_id: null,
}

function emptyCareDay(animals: AnimalView[] = []): CareDayView {
  return {
    id: 1,
    house_id: HOUSE_ID,
    plan_date: PLAN_DATE,
    starts_at: '2026-09-14T21:00:00Z',
    ends_at: '2026-09-15T21:00:00Z',
    steps: [],
    animals,
  }
}

export const STANDS: Record<StandId, StandData> = {
  no_access: {
    id: 'no_access',
    label: 'Нет доступа',
    user: null,
    house: null,
    careDay: null,
    appointments: [],
    nowHouseLocal: '11:00',
  },
  no_house: {
    id: 'no_house',
    label: 'Без дома',
    user: { id: 1, display_timezone: 'UTC', telegram_id: '10001' },
    house: null,
    careDay: null,
    appointments: [],
    nowHouseLocal: '11:00',
  },
  empty_house: {
    id: 'empty_house',
    label: 'Пустой дом',
    user: { ...userBangkok, display_timezone: 'Asia/Bangkok' },
    house: houseBangkok,
    careDay: emptyCareDay([]),
    appointments: [],
    nowHouseLocal: '11:00',
  },
  full_day: {
    id: 'full_day',
    label: 'Полный день',
    user: userBangkok,
    house: houseBangkok,
    careDay: careDayFull,
    appointments: appointmentsFull,
    nowHouseLocal: '11:15',
  },
  settings: {
    id: 'settings',
    label: 'Настройки',
    user: userBangkok,
    house: houseBangkok,
    careDay: careDayFull,
    appointments: appointmentsFull,
    nowHouseLocal: '11:15',
  },
}

export const STAND_ORDER: StandId[] = [
  'no_access',
  'no_house',
  'empty_house',
  'full_day',
  'settings',
]

export function cloneStand(id: StandId): StandData {
  return structuredClone(STANDS[id])
}
