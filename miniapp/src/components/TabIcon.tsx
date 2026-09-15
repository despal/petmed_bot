/** Simple tab glyphs in the same 28px circle as animal avatars. */

export function TabIcon({
  name,
  active,
}: {
  name: 'home' | 'settings' | 'add'
  active?: boolean
}) {
  return (
    <span className={`tab-icon${active ? ' active' : ''}`} aria-hidden>
      {name === 'home' && (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M12 3.2 3.5 10.2V21h6.2v-6.1h4.6V21h6.2V10.2L12 3.2Z" />
        </svg>
      )}
      {name === 'settings' && (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M19.1 12.9c.05-.3.05-.6 0-.9l1.7-1.3c.15-.12.2-.33.1-.5l-1.6-2.8c-.1-.17-.3-.24-.48-.18l-2 .8c-.4-.3-.84-.54-1.32-.7l-.3-2.1A.4.4 0 0 0 14.3 4h-3.2a.4.4 0 0 0-.4.34l-.3 2.1c-.48.16-.92.4-1.32.7l-2-.8a.4.4 0 0 0-.48.18L5.1 9.4a.4.4 0 0 0 .1.5l1.7 1.3c-.05.3-.05.6 0 .9l-1.7 1.3a.4.4 0 0 0-.1.5l1.6 2.8c.1.17.3.24.48.18l2-.8c.4.3.84.54 1.32.7l.3 2.1c.04.2.2.34.4.34h3.2c.2 0 .36-.14.4-.34l.3-2.1c.48-.16.92-.4 1.32-.7l2 .8c.18.06.38 0 .48-.18l1.6-2.8a.4.4 0 0 0-.1-.5l-1.7-1.3ZM12.7 14.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5Z" />
        </svg>
      )}
      {name === 'add' && (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />
        </svg>
      )}
    </span>
  )
}
