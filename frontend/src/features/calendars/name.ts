import type { TFunction } from 'i18next'
import type { Schemas } from '@/lib/api'

type Calendar = Pick<Schemas['CalendarOut'], 'name' | 'is_default'>
type SpaceKind = Schemas['SpaceKind']

/** A calendar's name to show. The API stores no name for a default calendar nobody
 *  renamed (`name: null`): the personal space's is „Mein Kalender“, the general
 *  space's „Allgemein“, in the reader's language; while its space is unknown
 *  (`spaceKind` undefined) „Standardkalender“, never a guess. */
export function calendarName(
  t: TFunction,
  calendar: Calendar,
  spaceKind: SpaceKind | undefined,
): string {
  if (calendar.name !== null) return calendar.name
  if (spaceKind === undefined) return t('calendars.default.unknown')
  return spaceKind === 'personal' ? t('calendars.default.personal') : t('calendars.default.general')
}
