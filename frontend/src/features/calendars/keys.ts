/** The query keys of calendars. Every key starts with `calendars`: a `resync` refreshes
 *  them all, a `calendar.changed` (ids only) what it can change (`live.ts`). */
export const calendarKeys = {
  all: ['calendars'] as const,
  /** The calendars of the spaces one belongs to (`GET /api/calendars`). */
  calendars: ['calendars', 'list'] as const,
  /** One space's calendars, the named way (`GET /api/spaces/{id}/calendars`). */
  spaces: ['calendars', 'space'] as const,
  space: (spaceId: string) => ['calendars', 'space', spaceId] as const,
  /** The spaces the calendars belong to: their names, kinds and one's roles. */
  spaceNames: ['calendars', 'space-names'] as const,
  /** The window's occurrences, keyed by what is asked. */
  windows: ['calendars', 'window'] as const,
  window: (params: object) => ['calendars', 'window', params] as const,
  /** One event (Task 11 shows it). */
  events: ['calendars', 'event'] as const,
  event: (eventId: string) => ['calendars', 'event', eventId] as const,
}
