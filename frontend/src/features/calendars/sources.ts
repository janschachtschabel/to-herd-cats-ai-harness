import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useMe } from '@/features/auth/queries'
import { isOwnPersonal } from '@/features/spaces/display'
import type { Space } from '@/lib/api'
import { calendarAbilities } from './abilities'
import type { CalendarGroup } from './CalendarList'
import type { CalendarInfo } from './display'
import { calendarName } from './name'
import { useCalendars, useCalendarSpaces, useNamedSpace, useSpaceCalendars } from './queries'

const KIND_ORDER: Record<Space['kind'], number> = { personal: 0, open: 1, team: 2 }

/** The calendars the page shows and how: one's own list, or with `spaceId` that space's
 *  (the named way); each worded (`name.ts`), toned and with the abilities of its
 *  space's `my_role`, grouped by space (one's personal space first). `spaces` is how
 *  the spaces' names stand: until they are known nothing is worded from a guessed
 *  kind or role (a default is „Standardkalender“, its space unnamed, no „nur lesen“). */
export function useCalendarSources(spaceId: string | undefined) {
  const { t } = useTranslation()
  const me = useMe()
  const own = useCalendars({ enabled: !spaceId })
  const inSpace = useSpaceCalendars(spaceId)
  const spaces = useCalendarSpaces({ enabled: !spaceId })
  const named = useNamedSpace(spaceId)
  const calendars = spaceId ? inSpace : own
  const spaceState = spaceId
    ? {
        isPending: named.isPending,
        isError: named.isError,
        error: named.error,
        refetch: () => void named.refetch(),
      }
    : spaces

  const spaceById = useMemo(() => {
    const map = new Map<string, Space>(spaces.items.map((space) => [space.id, space]))
    if (named.data) map.set(named.data.id, named.data)
    return map
  }, [spaces.items, named.data])

  const namesKnown = !spaceState.isPending && !spaceState.isError
  const myId = me?.user.id
  const { infos, groups } = useMemo(() => {
    const infos = new Map<string, CalendarInfo>()
    const bySpace = new Map<string, CalendarGroup>()
    for (const calendar of calendars.items) {
      const space = spaceById.get(calendar.space_id)
      const info: CalendarInfo = {
        label: calendarName(t, calendar, space?.kind),
        color: calendar.color,
        abilities: space ? calendarAbilities(space.my_role) : null,
      }
      infos.set(calendar.id, info)
      const group = bySpace.get(calendar.space_id) ?? {
        spaceId: calendar.space_id,
        spaceName: !space
          ? t(namesKnown ? 'calendar.list.unknownSpace' : 'calendar.list.spaceNotLoaded')
          : isOwnPersonal(space, myId)
            ? t('spaces.mine')
            : space.name,
        calendars: [],
      }
      group.calendars.push({ id: calendar.id, ...info })
      bySpace.set(calendar.space_id, group)
    }
    const rank = (group: CalendarGroup) => {
      const kind = spaceById.get(group.spaceId)?.kind
      return kind ? KIND_ORDER[kind] : 3
    }
    const groups = [...bySpace.values()].sort(
      (a, b) => rank(a) - rank(b) || a.spaceName.localeCompare(b.spaceName),
    )
    return { infos, groups }
  }, [calendars.items, spaceById, namesKnown, myId, t])

  return { calendars, spaces: spaceState, infos, groups, namedSpace: named.data }
}
