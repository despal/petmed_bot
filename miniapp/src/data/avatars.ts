export const AVATAR_KEYS = Array.from({ length: 20 }, (_, i) => {
  const n = String(i + 1).padStart(2, '0')
  return `img${n}`
})

export function avatarLabel(key: string): string {
  return key.toUpperCase()
}
