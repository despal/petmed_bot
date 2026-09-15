import { useMemo, useState } from 'react'
import {
  guessDeviceTimezone,
  placeCaption,
  TZ_PLACES,
} from '../data/timezones'

export function FirstTimezoneScreen({
  onConfirm,
}: {
  onConfirm: (iana: string) => void
}) {
  const guessed = useMemo(() => {
    const device = guessDeviceTimezone()
    if (TZ_PLACES.some((p) => p.iana === device)) return device
    return 'UTC'
  }, [])
  const [iana, setIana] = useState(guessed)
  const [confirmed, setConfirmed] = useState(false)

  return (
    <div className="panel" style={{ paddingTop: 32 }}>
      <h2>Пояс дома</h2>
      <p className="muted">
        Сутки ухода и слоты считаются по поясу дома. Подтверждение обязательно.
      </p>
      <div className="field">
        <label>Место</label>
        <select value={iana} onChange={(e) => setIana(e.target.value)}>
          {TZ_PLACES.map((p) => (
            <option key={p.iana} value={p.iana}>
              {placeCaption(p.iana)}
            </option>
          ))}
        </select>
      </div>
      <p>
        Выбрано: <strong>{placeCaption(iana)}</strong>
      </p>
      <label className="check-row">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        Подтверждаю пояс
      </label>
      <div className="btn-row">
        <button
          type="button"
          className="btn primary"
          disabled={!confirmed}
          onClick={() => onConfirm(iana)}
        >
          Создать дом
        </button>
      </div>
    </div>
  )
}
