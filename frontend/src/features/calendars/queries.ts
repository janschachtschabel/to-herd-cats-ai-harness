import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api, unwrap, type Schemas } from '@/lib/api'
import { spaceQuery } from '@/features/spaces/queries'
import { pagedQuery } from '@/lib/paging'
import { calendarKeys } from './keys'

export type Calendar = Schemas['CalendarOut']
export type Occurrence = Schemas['OccurrenceOut']

/** The window's pages: 100 occurrences each, the most the API gives. */
const PAGE_SIZE = 100

export const calendarsQuery = pagedQuery(calendarKeys.calendars, async (cursor) =>
  unwrap(await api.GET('/api/calendars', { params: { query: { cursor, limit: PAGE_SIZE } } })),
)

export const spaceCalendarsQuery = (spaceId: string) =>
  pagedQuery(calendarKeys.space(spaceId), async (cursor) =>
    unwrap(
      await api.GET('/api/spaces/{space_id}/calendars', {
        params: { path: { space_id: spaceId }, query: { cursor, limit: PAGE_SIZE } },
      }),
    ),
  )

/** The spaces one's calendars belong to, every page (without other people's
 *  personal spaces, whose calendars one does not list). */
export const calendarSpacesQuery = pagedQuery(calendarKeys.spaceNames, async (cursor) =>
  unwrap(
    await api.GET('/api/spaces', {
      params: { query: { cursor, limit: PAGE_SIZE, include_others_personal: false } },
    }),
  ),
)

/** What the window is asked for. `calendarIds`: only these calendars (an empty list
 *  asks nothing); `spaceId`: the named way, this space's events alone; `q`: titles. */
export interface WindowParams {
  from: string
  to: string
  timeZone: string
  calendarIds?: string[] | undefined
  spaceId?: string | undefined
  q?: string | undefined
}

export const windowQuery = (params: WindowParams) =>
  pagedQuery(calendarKeys.window(params), async (cursor) =>
    unwrap(
      await api.GET('/api/calendar/events', {
        params: {
          query: {
            from: params.from,
            to: params.to,
            time_zone: params.timeZone,
            calendar_ids: params.calendarIds,
            space_id: params.spaceId,
            q: params.q || undefined,
            cursor,
            limit: PAGE_SIZE,
          },
        },
      }),
    ),
  )

type Paged<T> = ReturnType<typeof pagedQuery<T>>

/** A paged list; `everything`: each next page is fetched as soon as the one before
 *  arrived (what is loaded shows at once), until the last or an error. */
function useLoaded<T>(options: Paged<T>, { everything = true, enabled = true } = {}) {
  const query = useInfiniteQuery({ ...options, enabled })
  const { hasNextPage, isFetchingNextPage, isError, fetchNextPage } = query
  useEffect(() => {
    if (everything && enabled && hasNextPage && !isFetchingNextPage && !isError)
      void fetchNextPage()
  }, [everything, enabled, hasNextPage, isFetchingNextPage, isError, fetchNextPage])
  return {
    items: query.data?.pages.flatMap((page) => page.items) ?? [],
    isPending: enabled && query.isPending,
    isError: query.isError,
    error: query.error,
    refetch: () => void query.refetch(),
    hasMore: query.hasNextPage,
    loadingMore: query.isFetchingNextPage,
    loadMore: () => void query.fetchNextPage(),
  }
}

/** The calendars of the spaces one belongs to (the first call makes one's defaults). */
export function useCalendars({ enabled = true } = {}) {
  return useLoaded(calendarsQuery, { enabled })
}

/** One space's calendars (for an admin outside it the named, audited way). */
export function useSpaceCalendars(spaceId: string | undefined) {
  return useLoaded(spaceCalendarsQuery(spaceId ?? ''), { enabled: Boolean(spaceId) })
}

/** The occurrences in a window. `everything` loads page after page (the grid views);
 *  without it the next page comes with `loadMore` (the agenda). */
export function useWindow(params: WindowParams, { everything = true } = {}) {
  const enabled = params.calendarIds === undefined || params.calendarIds.length > 0
  return useLoaded(windowQuery(params), { everything, enabled })
}

export function useCalendarSpaces({ enabled = true } = {}) {
  return useLoaded(calendarSpacesQuery, { enabled })
}

/** The space named in the address (`/calendar?space=<id>`), if any. */
export function useNamedSpace(spaceId: string | undefined) {
  return useQuery({ ...spaceQuery(spaceId ?? ''), enabled: Boolean(spaceId) })
}
