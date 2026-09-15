import { placeCaption, TZ_PLACES } from '../data/timezones'
import { AvatarBadge } from './Avatar'
import type { AnimalView, AppointmentView, HouseView, UserView } from '../types'

export function SettingsScreen({
  user,
  house,
  animals,
  appointments,
  theme,
  onThemeChange,
  onEditAnimal,
  onAddAnimal,
  onEditAppointment,
  onPickHouseTz,
  onPickMyTz,
}: {
  user: UserView
  house: HouseView
  animals: AnimalView[]
  appointments: AppointmentView[]
  theme: 'system' | 'light' | 'dark'
  onThemeChange: (t: 'system' | 'light' | 'dark') => void
  onEditAnimal: (id: number) => void
  onAddAnimal: () => void
  onEditAppointment: (id: number) => void
  onPickHouseTz: (iana: string) => void
  onPickMyTz: (iana: string) => void
}) {
  const liveAnimals = animals.filter((a) => !a.archived)
  const archivedAnimals = animals.filter((a) => a.archived)
  const liveAppts = appointments.filter((a) => !a.archived)
  const archivedAppts = appointments.filter((a) => a.archived)

  return (
    <div className="panel">
      <h2>Настройки</h2>

      <section className="settings-section">
        <h3>Животные</h3>
        {liveAnimals.map((a) => (
          <button
            key={a.id}
            type="button"
            className="list-item"
            onClick={() => onEditAnimal(a.id)}
          >
            <AvatarBadge avatarKey={a.avatar_key} size={36} />
            <span className="grow">{a.name}</span>
          </button>
        ))}
        <button type="button" className="btn" onClick={onAddAnimal}>
          Добавить животное
        </button>
        {archivedAnimals.length > 0 && (
          <>
            <p className="muted" style={{ marginTop: 12 }}>
              Архив
            </p>
            {archivedAnimals.map((a) => (
              <button
                key={a.id}
                type="button"
                className="list-item"
                onClick={() => onEditAnimal(a.id)}
              >
                <AvatarBadge avatarKey={a.avatar_key} size={36} />
                <span className="grow">{a.name}</span>
                <span className="muted">Включить</span>
              </button>
            ))}
          </>
        )}
      </section>

      <section className="settings-section">
        <h3>Назначения</h3>
        {liveAppts.map((a) => (
          <button
            key={a.id}
            type="button"
            className="list-item"
            onClick={() => onEditAppointment(a.id)}
          >
            <span className="grow">
              <strong>{a.title}</strong>
              <div className="muted">
                {a.animal_ids
                  .map(
                    (id) =>
                      animals.find((x) => x.id === id)?.name ?? `#${id}`,
                  )
                  .join(', ')}
              </div>
            </span>
          </button>
        ))}
        {archivedAppts.length > 0 && (
          <>
            <p className="muted">Выключенные</p>
            {archivedAppts.map((a) => (
              <div key={a.id} className="list-item">
                <span className="grow">
                  <strong>{a.title}</strong>
                  <div className="muted">архив</div>
                </span>
                <span className="muted">Включить</span>
              </div>
            ))}
          </>
        )}
      </section>

      <section className="settings-section">
        <h3>Время дома</h3>
        <p className="muted">
          Смена не пересобирает уже собранный сегодня день.
        </p>
        <div className="field">
          <label>{placeCaption(house.schedule_timezone)}</label>
          <select
            value={house.schedule_timezone}
            onChange={(e) => onPickHouseTz(e.target.value)}
          >
            {TZ_PLACES.map((p) => (
              <option key={p.iana} value={p.iana}>
                {placeCaption(p.iana)}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="settings-section">
        <h3>Моё время</h3>
        <div className="field">
          <label>{placeCaption(user.display_timezone)}</label>
          <select
            value={user.display_timezone}
            onChange={(e) => onPickMyTz(e.target.value)}
          >
            {TZ_PLACES.map((p) => (
              <option key={p.iana} value={p.iana}>
                {placeCaption(p.iana)}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="settings-section">
        <h3>Тема</h3>
        <div className="field">
          <select
            value={theme}
            onChange={(e) =>
              onThemeChange(e.target.value as 'system' | 'light' | 'dark')
            }
          >
            <option value="system">Как в системе</option>
            <option value="light">Светлая</option>
            <option value="dark">Тёмная</option>
          </select>
        </div>
      </section>
    </div>
  )
}
