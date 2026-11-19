import { isoToZoned, zonedToIso } from '@/features/automations/zoned'

/** Calendar days without a date library (plan M10 decision 17). A day is a plain
 *  `YYYY-MM-DD` string, counted on UTC dates so that no clock change moves it; only
 *  where a day meets instants (its start in a zone, an occurrence's day) does a zone
 *  come in. */
export type Day = string

export type CalendarView = 'month' | 'week' | 'day' | 'agenda'

export const VIEWS: readonly CalendarView[] = ['month', 'week', 'day', 'agenda']

/** How many days the agenda shows from its first day. */
export const AGENDA_DAYS = 30

const DAY_MS = 86_400_000

/** What the days of an occurrence depend on (the window's `OccurrenceOut`). */
export interface Timed {
  start: string
  end: string
  all_day: boolean
}

function toUtc(day: Day): number {
  const [y, m, d] = day.split('-').map(Number)
  return Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)
}

function fromUtc(ms: number): Day {
  return new Date(ms).toISOString().slice(0, 10)
}

export function addDays(day: Day, days: number): Day {
  return fromUtc(toUtc(day) + days * DAY_MS)
}

/** ISO weekday: 1 Monday … 7 Sunday. */
export function weekday(day: Day): number {
  return ((new Date(toUtc(day)).getUTCDay() + 6) % 7) + 1
}

const SUNDAY_REGIONS = new Set(['US', 'CA', 'BR', 'JP', 'IL', 'MX', 'PH', 'KR', 'IN', 'ZA', 'AU'])
const SATURDAY_REGIONS = new Set(['EG', 'SA', 'AE', 'IR', 'DZ', 'KW', 'QA', 'BH', 'OM', 'JO'])

interface WeekInfo {
  firstDay: number
}

/** The first day of the week in `locale` (ISO weekday): what the browser knows, else
 *  the region's custom. */
export function weekStart(locale: string): number {
  try {
    const loc = new Intl.Locale(locale) as Intl.Locale & {
      getWeekInfo?: () => WeekInfo
      weekInfo?: WeekInfo
    }
    const info = loc.getWeekInfo?.() ?? loc.weekInfo
    if (info) return info.firstDay
    const region = loc.maximize().region ?? ''
    if (SUNDAY_REGIONS.has(region)) return 7
    if (SATURDAY_REGIONS.has(region)) return 6
  } catch {
    // An unknown locale: the ISO week.
  }
  return 1
}

export function startOfWeek(day: Day, locale: string): Day {
  return addDays(day, -((weekday(day) - weekStart(locale) + 7) % 7))
}

function firstOfMonth(day: Day): Day {
  return `${day.slice(0, 7)}-01`
}

function lastOfMonth(day: Day): Day {
  const [y, m] = day.split('-').map(Number)
  return fromUtc(Date.UTC(y ?? 1970, m ?? 1, 0))
}

/** The weeks that show the month of `day`: whole weeks from the week start. */
export function monthGrid(day: Day, locale: string): Day[][] {
  const first = startOfWeek(firstOfMonth(day), locale)
  const last = addDays(startOfWeek(lastOfMonth(day), locale), 6)
  const weeks: Day[][] = []
  for (let start = first; start <= last; start = addDays(start, 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(start, i)))
  }
  return weeks
}

/** The first and last day a view shows around `anchor`. */
export function rangeOf(
  view: CalendarView,
  anchor: Day,
  locale: string,
): { first: Day; last: Day } {
  switch (view) {
    case 'month': {
      const weeks = monthGrid(anchor, locale)
      return { first: weeks[0]![0]!, last: weeks.at(-1)!.at(-1)! }
    }
    case 'week': {
      const first = startOfWeek(anchor, locale)
      return { first, last: addDays(first, 6) }
    }
    case 'day':
      return { first: anchor, last: anchor }
    case 'agenda':
      return { first: anchor, last: addDays(anchor, AGENDA_DAYS - 1) }
  }
}

/** The anchor one step back (`-1`) or on (`1`): a month starts on its first day. */
export function shiftAnchor(view: CalendarView, anchor: Day, step: 1 | -1): Day {
  switch (view) {
    case 'month': {
      const [y, m] = anchor.split('-').map(Number)
      return fromUtc(Date.UTC(y ?? 1970, (m ?? 1) - 1 + step, 1))
    }
    case 'week':
      return addDays(anchor, 7 * step)
    case 'day':
      return addDays(anchor, step)
    case 'agenda':
      return addDays(anchor, AGENDA_DAYS * step)
  }
}

/** The instant a day begins in `zone` (ISO, UTC); a midnight the clock skips is the
 *  first time that exists. */
export function dayStart(day: Day, zone: string): string {
  const guess = zonedToIso(day, '00:00', zone)
  if (guess === null) return `${day}T00:00:00.000Z`
  // In a gap at midnight the guess can land on the evening before: move it on by
  // what its wall clock lacks to midnight, which is the moment the clock jumps.
  const wall = isoToZoned(guess, zone)
  if (wall.date >= day) return guess
  const [h, m] = wall.time.split(':').map(Number)
  const short = DAY_MS - ((h ?? 0) * 60 + (m ?? 0)) * 60_000
  return new Date(new Date(guess).getTime() + short).toISOString()
}

/** The window to ask for: from the first day's start to the start of the day after
 *  the last, in the viewer's zone. */
export function windowOf(range: { first: Day; last: Day }, zone: string) {
  return { from: dayStart(range.first, zone), to: dayStart(addDays(range.last, 1), zone) }
}

export function todayIn(zone: string, now: Date = new Date()): Day {
  return isoToZoned(now.toISOString(), zone).date
}

function dayIn(iso: string, zone: string): Day {
  return isoToZoned(iso, zone).date
}

/** The day an occurrence starts on for the viewer. An all-day one floats on 00:00 UTC
 *  of its days (the API's form): its days are the same in every zone. */
export function dayOf(occurrence: Timed, zone: string): Day {
  return occurrence.all_day ? occurrence.start.slice(0, 10) : dayIn(occurrence.start, zone)
}

/** Every day an occurrence touches for the viewer; one that ends at a midnight does
 *  not reach the day after. */
export function daysOf(occurrence: Timed, zone: string): Day[] {
  const first = dayOf(occurrence, zone)
  const endMs = new Date(occurrence.end).getTime() - 1
  const last = occurrence.all_day
    ? fromUtc(Math.max(endMs, toUtc(first)))
    : dayIn(new Date(Math.max(endMs, new Date(occurrence.start).getTime())).toISOString(), zone)
  const days: Day[] = []
  for (let day = first; day <= last; day = addDays(day, 1)) days.push(day)
  return days
}
