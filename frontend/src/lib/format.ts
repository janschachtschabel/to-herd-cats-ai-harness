/** A timestamp from the API in the reader's language, e.g. "12.11.2026, 21:30". */
export function formatDateTime(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  )
}

/** A file size in the reader's language, e.g. "1,5 MB". */
export function formatBytes(bytes: number, locale: string): string {
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)} ${units[unit]}`
}

/** A calendar day from the API (`2026-11-20`, no time, no zone) in the reader's
 *  language, e.g. "20.11.2026"; read as that day wherever the reader is. */
export function formatDay(value: string, locale: string): string {
  const [year, month, day] = value.split('-').map(Number)
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(
    new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1),
  )
}

/** A count for a badge: above 99 it reads "99+". */
export function badgeCount(count: number): string {
  return count > 99 ? '99+' : String(count)
}
