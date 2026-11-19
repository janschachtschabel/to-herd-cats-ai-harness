/** The query keys of calendars. Every key starts with `calendars`: a `calendar.changed`
 *  (ids only, plan M10) or a `resync` refreshes them all; the views (Task 10) hang
 *  their lists, windows and events below it. */
export const calendarKeys = {
  all: ['calendars'] as const,
}
