import type { Schemas } from '@/lib/api'
import { calendarAbilities } from '@/features/calendars/abilities'
import type { CalendarInfo } from '@/features/calendars/display'

type Calendar = Schemas['CalendarOut']
type Occurrence = Schemas['OccurrenceOut']

let counter = 0
const nextId = () => `00000000-0000-4000-8000-${String(++counter).padStart(12, '0')}`

export function makeCalendar(overrides: Partial<Calendar> = {}): Calendar {
  return {
    id: nextId(),
    space_id: nextId(),
    name: 'Team',
    color: 'blue',
    is_default: false,
    time_zone: 'Europe/Berlin',
    version: 1,
    ...overrides,
  }
}

export function makeOccurrence(overrides: Partial<Occurrence> = {}): Occurrence {
  return {
    event_id: nextId(),
    calendar_id: 'cal-1',
    space_id: 'space-1',
    series_id: null,
    start: '2026-11-19T09:00:00Z',
    end: '2026-11-19T10:00:00Z',
    all_day: false,
    recurring: false,
    recurrence_id: null,
    title: 'Teamrunde',
    location: null,
    status: 'confirmed',
    visibility: 'default',
    busy: true,
    redacted: false,
    ...overrides,
  }
}

/** The views' calendar lookup: `cal-1` „Team“ (blue, editor). */
export function calendarInfos(): Map<string, CalendarInfo> {
  return new Map([
    ['cal-1', { label: 'Team', color: 'blue', abilities: calendarAbilities('editor') }],
  ])
}
