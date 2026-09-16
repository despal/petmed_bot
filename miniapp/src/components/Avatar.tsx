import { AVATAR_KEYS } from '../data/avatars'

function avatarSrc(key: string): string {
  return `/avatars/${key}.png`
}

export function AvatarBadge({
  avatarKey,
  size = 28,
}: {
  avatarKey: string | null
  size?: number
}) {
  const key = avatarKey && AVATAR_KEYS.includes(avatarKey) ? avatarKey : 'img01'
  return (
    <span
      className="tab-avatar"
      style={{ width: size, height: size }}
      title={key}
    >
      <img src={avatarSrc(key)} alt="" width={size} height={size} draggable={false} />
    </span>
  )
}

export function AvatarPicker({
  value,
  onChange,
}: {
  value: string | null
  onChange: (key: string) => void
}) {
  return (
    <div className="avatar-grid">
      {AVATAR_KEYS.map((key) => (
        <button
          key={key}
          type="button"
          className={`avatar-pick${value === key ? ' selected' : ''}`}
          onClick={() => onChange(key)}
        >
          <AvatarBadge avatarKey={key} size={40} />
        </button>
      ))}
    </div>
  )
}
