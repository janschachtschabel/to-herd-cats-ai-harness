/** A timestamp from the API in the reader's language, e.g. "12.11.2026, 21:30". */
export function formatDateTime(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  )
}
