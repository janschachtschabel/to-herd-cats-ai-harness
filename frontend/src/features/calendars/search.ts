import { VIEWS, type CalendarView, type Day } from './dates'

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const DAY = /^(19\d\d|2[0-3]\d\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/

/** The calendar's address: `space` (the named way: one space's calendars), `view` and
 *  `date` (the day the view shows; today when left out). */
export interface CalendarSearch {
  space?: string | undefined
  view?: CalendarView | undefined
  date?: Day | undefined
}

function isDay(value: unknown): value is Day {
  if (typeof value !== 'string' || !DAY.test(value)) return false
  return new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value
}

/** Every key, undefined when refused (see app/router/search.ts). */
export function calendarSearch(search: Record<string, unknown>): CalendarSearch {
  const space = typeof search.space === 'string' && ID.test(search.space) ? search.space : undefined
  const view = VIEWS.includes(search.view as CalendarView)
    ? (search.view as CalendarView)
    : undefined
  return { space: space?.toLowerCase(), view, date: isDay(search.date) ? search.date : undefined }
}
