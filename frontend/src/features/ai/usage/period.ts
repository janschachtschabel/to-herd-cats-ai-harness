const DAY_MS = 86_400_000

/** A UTC day as `YYYY-MM-DD`. */
export function utcDay(date: Date): string {
  return date.toISOString().slice(0, 10)
}

/** The last 30 UTC days up to `now` (the backend's own default). */
export function lastThirtyDays(now: Date = new Date()): { from: string; to: string } {
  return { from: utcDay(new Date(now.getTime() - 29 * DAY_MS)), to: utcDay(now) }
}

/** A cost (decimal string) in the person's locale, or null where nothing was priced. */
export function formatCost(cost: string | null, locale: string): string | null {
  if (cost === null) return null
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 4 }).format(Number(cost))
}
