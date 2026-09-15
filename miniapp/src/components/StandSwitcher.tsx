import { STAND_ORDER } from '../data/stands'
import type { StandId } from '../types'
import { STANDS } from '../data/stands'

export function StandSwitcher({
  standId,
  onChange,
}: {
  standId: StandId
  onChange: (id: StandId) => void
}) {
  return (
    <div className="dev-bar">
      <label>
        Стенд
        <select
          value={standId}
          onChange={(e) => onChange(e.target.value as StandId)}
        >
          {STAND_ORDER.map((id) => (
            <option key={id} value={id}>
              {STANDS[id].label}
            </option>
          ))}
        </select>
      </label>
      <span className="hint">моки · без ядра</span>
    </div>
  )
}
