import { useState } from 'react'
import { AvatarPicker } from './Avatar'
import type { AnimalView } from '../types'
import { AVATAR_KEYS } from '../data/avatars'

export function AnimalForm({
  animal,
  usedKeys,
  onClose,
  onSave,
}: {
  animal?: AnimalView
  usedKeys: string[]
  onClose: () => void
  onSave: (name: string, avatarKey: string) => void
}) {
  const firstFree =
    AVATAR_KEYS.find((k) => !usedKeys.includes(k)) ?? AVATAR_KEYS[0]
  const [name, setName] = useState(animal?.name ?? '')
  const [avatarKey, setAvatarKey] = useState(
    animal?.avatar_key ?? firstFree,
  )
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-top">
          <h2>{animal ? 'Животное' : 'Добавить животное'}</h2>
          <button type="button" className="icon-btn" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="field">
          <label>Имя</label>
          <input
            value={name}
            maxLength={200}
            onChange={(e) => setName(e.target.value)}
            placeholder="Север"
          />
        </div>
        <div className="field">
          <label>Картинка</label>
          <AvatarPicker value={avatarKey} onChange={setAvatarKey} />
        </div>
        {error && <p className="error-text">{error}</p>}
        <div className="btn-row">
          <button type="button" className="btn" onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={() => {
              if (!name.trim()) {
                setError('Имя обязательно')
                return
              }
              onSave(name.trim(), avatarKey)
            }}
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}
