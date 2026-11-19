import type { TFunction } from 'i18next'
import type { Schemas } from '@/lib/api'
import type { CalendarAbilities } from './abilities'
import { dayOf, daysOf, type Day } from './dates'
import type { Occurrence } from './queries'

export type CalendarColor = Schemas['CalendarColor']

/** What the views show of a calendar: its worded name, tone, and what one may do
 *  (null while its space's role is not known). */
export interface CalendarInfo {
  label: string
  color: CalendarColor
  abilities: CalendarAbilities | null
}

/** A calendar's name in chips, the agenda and the look at an event; one the list does
 *  not hold (an event one sees in another space's calendar) is „Kalender“. */
export function calendarLabel(t: TFunction, calendar: CalendarInfo | undefined): string {
  return calendar?.label ?? t('calendar.event.otherCalendar')
}

/** The eight fixed tones (plan M10 decision 17) as a dot and a chip's edge. Colour is
 *  never the only sign: every event names its calendar to screen readers, and text
 *  stays in the theme's foreground on its background (WCAG 2.2 AA). Each tone has at
 *  least 3:1 (WCAG 1.4.11) against the page, `muted` (a chip) and `accent` (a chip
 *  under the pointer) in its theme: light at least 3.16 (teal-600 on accent), dark at
 *  least 5.04 (red-400 on accent), measured from the oklch values. */
export const TONE_DOT: Record<CalendarColor, string> = {
  blue: 'bg-blue-600 dark:bg-blue-400',
  green: 'bg-green-700 dark:bg-green-400',
  amber: 'bg-amber-700 dark:bg-amber-400',
  red: 'bg-red-600 dark:bg-red-400',
  violet: 'bg-violet-600 dark:bg-violet-400',
  teal: 'bg-teal-600 dark:bg-teal-400',
  pink: 'bg-pink-600 dark:bg-pink-400',
  slate: 'bg-slate-500 dark:bg-slate-400',
}

export const TONE_EDGE: Record<CalendarColor, string> = {
  blue: 'border-l-blue-600 dark:border-l-blue-400',
  green: 'border-l-green-700 dark:border-l-green-400',
  amber: 'border-l-amber-700 dark:border-l-amber-400',
  red: 'border-l-red-600 dark:border-l-red-400',
  violet: 'border-l-violet-600 dark:border-l-violet-400',
  teal: 'border-l-teal-600 dark:border-l-teal-400',
  pink: 'border-l-pink-600 dark:border-l-pink-400',
  slate: 'border-l-slate-500 dark:border-l-slate-400',
}

/** The title to show: „Belegt“ for what one sees only as busy, never a title. */
export function eventTitle(t: TFunction, occurrence: Occurrence): string {
  if (occurrence.redacted) return t('calendar.event.busy')
  return occurrence.title?.trim() || t('calendar.event.untitled')
}

const timeFormat = (locale: string, zone: string) =>
  new Intl.DateTimeFormat(locale, { timeStyle: 'short', timeZone: zone })

export function startTime(occurrence: Occurrence, zone: string, locale: string): string {
  return timeFormat(locale, zone).format(new Date(occurrence.start))
}

/** The time a one-line chip shows on `day`: the start on the day the occurrence starts;
 *  on a later day („bis 02:00“ on its last, „Fortsetzung“ between) never the start as
 *  if it began there. None for all-day ones. */
export function chipTime(
  t: TFunction,
  occurrence: Occurrence,
  day: Day | undefined,
  zone: string,
  locale: string,
): string | null {
  if (occurrence.all_day) return null
  if (day === undefined || day <= dayOf(occurrence, zone))
    return startTime(occurrence, zone, locale)
  if (day === daysOf(occurrence, zone).at(-1))
    return t('calendar.event.until', {
      time: timeFormat(locale, zone).format(new Date(occurrence.end)),
    })
  return t('calendar.event.continued')
}

/** When an occurrence is, for the look at it: its day and times, or for an all-day
 *  one its day or days („Donnerstag, 19. – Samstag, 21. November 2026, ganztägig“). */
export function whenText(t: TFunction, occurrence: Occurrence, zone: string, locale: string) {
  const days = daysOf(occurrence, zone)
  const first = days[0]!
  const last = days.at(-1)!
  const date =
    occurrence.all_day && last !== first
      ? formatDayRange(first, last, locale)
      : formatDay(first, locale)
  return `${date}, ${timeRange(t, occurrence, zone, locale)}`
}

/** "10:00–11:00", or „ganztägig“; a timed one over several days names its dates. */
export function timeRange(
  t: TFunction,
  occurrence: Occurrence,
  zone: string,
  locale: string,
): string {
  if (occurrence.all_day) return t('calendar.event.allDay')
  const start = new Date(occurrence.start)
  const end = new Date(occurrence.end)
  const sameDay =
    end.getTime() - start.getTime() < 86_400_000 &&
    dayLabel(start.toISOString(), zone, locale) ===
      dayLabel(new Date(end.getTime() - 1).toISOString(), zone, locale)
  const format = sameDay
    ? timeFormat(locale, zone)
    : new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'short', timeZone: zone })
  return format.formatRange(start, end)
}

function dayLabel(iso: string, zone: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeZone: zone }).format(
    new Date(iso),
  )
}

const asUtc = (day: Day) => new Date(`${day}T00:00:00Z`)

/** A day in words: "Donnerstag, 19. November 2026" (`full`) or shorter. */
export function formatDay(
  day: Day,
  locale: string,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'full' },
): string {
  return new Intl.DateTimeFormat(locale, { ...options, timeZone: 'UTC' }).format(asUtc(day))
}

/** A range of days in words, shortened where they share month and year. */
export function formatDays(first: Day, last: Day, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).formatRange(asUtc(first), asUtc(last))
}

/** A range of days in full words, for the look at an all-day event of several days. */
export function formatDayRange(first: Day, last: Day, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'full', timeZone: 'UTC' }).formatRange(
    asUtc(first),
    asUtc(last),
  )
}

export function formatMonth(day: Day, locale: string): string {
  return formatDay(day, locale, { month: 'long', year: 'numeric' })
}

/** All-day ones first, then by start, then the longer first. */
export function byStart(a: Occurrence, b: Occurrence): number {
  if (a.all_day !== b.all_day) return a.all_day ? -1 : 1
  return Date.parse(a.start) - Date.parse(b.start) || Date.parse(b.end) - Date.parse(a.end)
}

/** A stable key for an occurrence: an event and which of its occurrences. */
export function occurrenceKey(occurrence: Occurrence): string {
  return `${occurrence.event_id}/${occurrence.recurrence_id ?? occurrence.start}`
}
