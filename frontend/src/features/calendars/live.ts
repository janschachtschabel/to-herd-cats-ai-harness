import { calendarKeys } from './keys'

type Key = readonly unknown[]

/** What a `calendar.changed` (ids only: the space and the calendar) can change: the
 *  lists of calendars that show the space (one's own, the space's), every window (a
 *  window spans spaces) and the events shown (the event is not named). Without the
 *  space, every calendar query. Content never comes from the event: these refetch. */
export function calendarEventKeys(spaceId: string | null): Key[] {
  if (!spaceId) return [calendarKeys.all]
  return [
    calendarKeys.calendars,
    calendarKeys.space(spaceId),
    calendarKeys.windows,
    calendarKeys.events,
  ]
}
