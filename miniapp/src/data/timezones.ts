/** Built-in place list for timezone pickers. Offset computed at display time. */

export interface TzPlace {
  iana: string
  label: string
}

export const TZ_PLACES: TzPlace[] = [
  { iana: 'Asia/Bangkok', label: 'Бангкок' },
  { iana: 'Europe/Moscow', label: 'Москва' },
  { iana: 'Europe/Kaliningrad', label: 'Калининград' },
  { iana: 'Asia/Yekaterinburg', label: 'Екатеринбург' },
  { iana: 'Asia/Novosibirsk', label: 'Новосибирск' },
  { iana: 'Asia/Vladivostok', label: 'Владивосток' },
  { iana: 'Europe/Berlin', label: 'Берлин' },
  { iana: 'Europe/London', label: 'Лондон' },
  { iana: 'America/New_York', label: 'Нью-Йорк' },
  { iana: 'UTC', label: 'UTC' },
]

export function utcOffsetLabel(iana: string, at: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: iana,
      timeZoneName: 'shortOffset',
    }).formatToParts(at)
    const raw = parts.find((p) => p.type === 'timeZoneName')?.value ?? 'UTC'
    // GMT+7 → UTC+7
    return raw.replace('GMT', 'UTC').replace('UTC+0', 'UTC').replace('UTC-0', 'UTC')
  } catch {
    return 'UTC'
  }
}

export function placeCaption(iana: string, at: Date = new Date()): string {
  const place = TZ_PLACES.find((p) => p.iana === iana)
  const name = place?.label ?? iana
  return `${name} (${utcOffsetLabel(iana, at)})`
}

export function guessDeviceTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}
