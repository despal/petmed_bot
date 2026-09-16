import { useEffect, useMemo, useState } from 'react'
import type { AnimalView, AppointmentView } from '../types'

export type AppointmentSavePayload = {
  title: string
  kind: AppointmentView['kind']
  animal_ids: number[]
  local_time?: string
  slot?: string
  reference_local_time?: string
  anchor_appointment_id?: number
  direction?: 'before' | 'after'
  offset_minutes?: number
  course_days?: number | null
  silent: boolean
}

export function AppointmentForm({
  appointment,
  animals,
  appointments,
  presetAnimalId,
  onClose,
  onSave,
}: {
  appointment?: AppointmentView
  animals: AnimalView[]
  appointments: AppointmentView[]
  presetAnimalId?: number
  onClose: () => void
  onSave: (payload: AppointmentSavePayload) => void
}) {
  const editing = Boolean(appointment)
  const liveAnimals = animals.filter((a) => !a.archived)

  const [title, setTitle] = useState(appointment?.title ?? '')
  const [kind, setKind] = useState<AppointmentView['kind']>(
    appointment?.kind ?? 'window',
  )
  const [slot, setSlot] = useState<'morning' | 'day' | 'evening'>(
    appointment?.slot ?? 'morning',
  )
  const [refTime, setRefTime] = useState(
    appointment?.reference_local_time ??
      appointment?.local_time ??
      '10:30',
  )
  const [course, setCourse] = useState(
    appointment?.course_days?.toString() ?? '',
  )
  const [silent, setSilent] = useState(appointment?.silent ?? false)
  const [selected, setSelected] = useState<number[]>(() => {
    if (appointment) return [...appointment.animal_ids]
    if (presetAnimalId) return [presetAnimalId]
    return liveAnimals[0] ? [liveAnimals[0].id] : []
  })
  const [anchorId, setAnchorId] = useState(
    appointment?.anchor_appointment_id?.toString() ?? '',
  )
  const [direction, setDirection] = useState<'before' | 'after'>(
    appointment?.direction ?? 'before',
  )
  const [offsetMin, setOffsetMin] = useState(
    appointment?.offset_minutes?.toString() ?? '30',
  )
  const [error, setError] = useState<string | null>(null)

  // Якоря: живые шаблоны дома, где есть хотя бы один из выбранных участников
  // (личные и общие). Чужие персональные и архив — скрыты. Себя — нет.
  const liveAnchors = useMemo(
    () =>
      appointments.filter(
        (a) =>
          !a.archived &&
          a.id !== appointment?.id &&
          a.animal_ids.some((id) => selected.includes(id)),
      ),
    [appointments, appointment?.id, selected],
  )

  useEffect(() => {
    if (anchorId && !liveAnchors.some((a) => String(a.id) === anchorId)) {
      setAnchorId('')
    }
  }, [anchorId, liveAnchors])

  useEffect(() => {
    if (!editing && kind === 'relative' && liveAnchors.length === 0) {
      setKind('window')
    }
  }, [editing, kind, liveAnchors.length])

  const toggleAnimal = (id: number) => {
    if (editing) return
    setSelected((prev) => {
      if (prev.includes(id)) {
        if (prev.length <= 1) return prev
        return prev.filter((x) => x !== id)
      }
      return [...prev, id]
    })
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-top">
          <h2>{editing ? 'Изменить назначение' : 'Новое назначение'}</h2>
          <button type="button" className="icon-btn" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="field">
          <label>Название</label>
          <input
            value={title}
            maxLength={300}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Антепсин"
          />
        </div>

        {!editing && (
          <div className="field">
            <label>Тип</label>
            <select
              value={kind}
              onChange={(e) =>
                setKind(e.target.value as AppointmentView['kind'])
              }
            >
              <option value="fixed">Жёсткое</option>
              <option value="window">Окно</option>
              <option
                value="relative"
                disabled={liveAnchors.length === 0}
              >
                Связное
                {liveAnchors.length === 0 ? ' (нет якоря)' : ''}
              </option>
            </select>
          </div>
        )}
        {editing && (
          <p className="muted">
            Тип: {kindRu(appointment!.kind)} (не меняется)
          </p>
        )}

        {kind === 'window' && (
          <>
            <div className="field">
              <label>Слот</label>
              <select
                value={slot}
                onChange={(e) =>
                  setSlot(e.target.value as 'morning' | 'day' | 'evening')
                }
              >
                <option value="morning">Утро</option>
                <option value="day">День</option>
                <option value="evening">Вечер</option>
              </select>
            </div>
            <div className="field">
              <label>Референс (время дома)</label>
              <input
                type="time"
                value={refTime ?? '10:30'}
                onChange={(e) => setRefTime(e.target.value)}
              />
            </div>
          </>
        )}

        {kind === 'fixed' && (
          <div className="field">
            <label>Время дома</label>
            <input
              type="time"
              value={refTime ?? '10:00'}
              onChange={(e) => setRefTime(e.target.value)}
            />
          </div>
        )}

        {kind === 'relative' && (
          <>
            <div className="field">
              <label>Якорь</label>
              <select
                value={anchorId}
                onChange={(e) => setAnchorId(e.target.value)}
                disabled={editing}
              >
                <option value="">Выберите…</option>
                {liveAnchors.map((a) => (
                  <option key={a.id} value={a.id}>
                    {anchorOptionLabel(a, animals, appointments)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Смещение</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <select
                  value={direction}
                  onChange={(e) =>
                    setDirection(e.target.value as 'before' | 'after')
                  }
                  disabled={editing}
                >
                  <option value="before">за … до</option>
                  <option value="after">через … после</option>
                </select>
                <input
                  type="number"
                  min={0}
                  value={offsetMin}
                  onChange={(e) => setOffsetMin(e.target.value)}
                  style={{ width: 100 }}
                  disabled={editing}
                />
                <span className="muted">мин</span>
              </div>
            </div>
          </>
        )}

        <div className="field">
          <label>Участники</label>
          {editing ? (
            <p className="muted" style={{ margin: 0 }}>
              {selected
                .map((id) => liveAnimals.find((a) => a.id === id)?.name ?? `#${id}`)
                .join(', ')}{' '}
              (состав при правке не меняем)
            </p>
          ) : (
            liveAnimals.map((a) => (
              <label key={a.id} className="check-row">
                <input
                  type="checkbox"
                  checked={selected.includes(a.id)}
                  onChange={() => toggleAnimal(a.id)}
                />
                {a.name}
              </label>
            ))
          )}
        </div>

        <div className="field">
          <label>Курс (дней, необязательно)</label>
          <input
            type="number"
            min={1}
            value={course}
            onChange={(e) => setCourse(e.target.value)}
            placeholder="—"
          />
        </div>

        <label className="check-row">
          <input
            type="checkbox"
            checked={silent}
            onChange={(e) => setSilent(e.target.checked)}
          />
          Без напоминаний
        </label>

        <p className="muted">Время на форме — пояс дома</p>
        {error && <p className="error-text">{error}</p>}

        <div className="btn-row">
          <button type="button" className="btn" onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={() => {
              if (!title.trim()) {
                setError('Название обязательно')
                return
              }
              if (!editing && selected.length === 0) {
                setError('Нужен хотя бы один участник')
                return
              }
              if (!editing && kind === 'relative' && !anchorId) {
                setError('Выберите якорь')
                return
              }
              const payload: AppointmentSavePayload = {
                title: title.trim(),
                kind,
                animal_ids: selected,
                silent,
                course_days: course ? Number(course) : null,
              }
              if (kind === 'fixed') {
                payload.local_time = refTime || '10:00'
              }
              if (kind === 'window') {
                payload.slot = slot
                payload.reference_local_time = refTime || '10:30'
              }
              if (kind === 'relative') {
                payload.anchor_appointment_id = Number(anchorId)
                payload.direction = direction
                payload.offset_minutes = Number(offsetMin) || 0
              }
              onSave(payload)
            }}
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}

function kindRu(k: AppointmentView['kind']): string {
  if (k === 'fixed') return 'жёсткое'
  if (k === 'window') return 'окно'
  return 'связное'
}

function slotRu(slot: string | null): string {
  if (slot === 'morning') return 'утро'
  if (slot === 'day') return 'день'
  if (slot === 'evening') return 'вечер'
  return ''
}

function animalNamesLine(
  animalIds: number[],
  animals: AnimalView[],
): string {
  return animalIds
    .map((id) => animals.find((a) => a.id === id)?.name ?? `#${id}`)
    .join(', ')
}

/** Подпись якоря: название · участники · время/слот */
function anchorOptionLabel(
  a: AppointmentView,
  animals: AnimalView[],
  all: AppointmentView[],
): string {
  const who = animalNamesLine(a.animal_ids, animals)
  let when = ''
  if (a.kind === 'fixed') {
    when = a.local_time ?? ''
  } else if (a.kind === 'window') {
    const slot = slotRu(a.slot)
    const ref = a.reference_local_time ? `~${a.reference_local_time}` : ''
    when = [slot, ref].filter(Boolean).join(' ')
  } else {
    const parent = all.find((x) => x.id === a.anchor_appointment_id)
    const dir = a.direction === 'before' ? 'до' : 'после'
    when = `${dir} «${parent?.title ?? '?'}»`
  }
  return [a.title, who, when].filter(Boolean).join(' · ')
}
