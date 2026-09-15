import { AVATAR_KEYS, avatarLabel } from '../data/avatars'

const HUES = [
  200, 140, 30, 280, 170, 340, 220, 50, 90, 310, 15, 190, 260, 70, 120, 0, 230,
  160, 45, 300,
]

export function AvatarBadge({
  avatarKey,
  size = 28,
}: {
  avatarKey: string | null
  size?: number
}) {
  const key = avatarKey && AVATAR_KEYS.includes(avatarKey) ? avatarKey : 'img01'
  const idx = AVATAR_KEYS.indexOf(key)
  const hue = HUES[idx] ?? 200
  return (
    <span
      className="tab-avatar"
      style={{
        width: size,
        height: size,
        fontSize: size < 36 ? 9 : 12,
        background: `hsl(${hue} 35% 42%)`,
        color: '#fff',
      }}
      title={key}
    >
      {avatarLabel(key)}
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
