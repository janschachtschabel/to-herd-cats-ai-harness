import type { Day } from '../dates'
import type { CalendarInfo } from '../display'
import type { Occurrence } from '../queries'

/** What every view takes: the loaded occurrences, the calendars by id, the viewer's
 *  zone and day, and what opening an event does. */
export interface ViewProps {
  occurrences: Occurrence[]
  calendars: ReadonlyMap<string, CalendarInfo>
  zone: string
  today: Day
  onOpen: (occurrence: Occurrence) => void
}
