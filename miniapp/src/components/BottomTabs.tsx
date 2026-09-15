import { AvatarBadge } from './Avatar'
import { TabIcon } from './TabIcon'
import type { AnimalView, TabId } from '../types'

export function BottomTabs({
  tab,
  animals,
  onChange,
  showAddAnimal,
  onAddAnimal,
}: {
  tab: TabId
  animals: AnimalView[]
  onChange: (tab: TabId) => void
  showAddAnimal?: boolean
  onAddAnimal?: () => void
}) {
  const live = animals.filter((a) => !a.archived)

  return (
    <nav className="bottom-tabs">
      <button
        type="button"
        className={tab === 'home' ? 'active' : ''}
        onClick={() => onChange('home')}
      >
        <TabIcon name="home" active={tab === 'home'} />
        Дом
      </button>
      {live.map((a) => {
        const id: TabId = `animal:${a.id}`
        return (
          <button
            key={a.id}
            type="button"
            className={tab === id ? 'active' : ''}
            onClick={() => onChange(id)}
          >
            <AvatarBadge avatarKey={a.avatar_key} />
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: '100%',
              }}
            >
              {a.name}
            </span>
          </button>
        )
      })}
      {showAddAnimal && (
        <button type="button" onClick={onAddAnimal}>
          <TabIcon name="add" />
          Животное
        </button>
      )}
      <button
        type="button"
        className={tab === 'settings' ? 'active' : ''}
        onClick={() => onChange('settings')}
      >
        <TabIcon name="settings" active={tab === 'settings'} />
        Настройки
      </button>
    </nav>
  )
}
