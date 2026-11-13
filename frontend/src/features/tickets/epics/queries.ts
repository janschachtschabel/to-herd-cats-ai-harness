import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { ticketKeys } from '../keys'

/** A space's epics with how far their children are, newest first. */
export const epicsQuery = (spaceId: string) =>
  pagedQuery(ticketKeys.epics(spaceId), async (cursor) =>
    unwrap(
      await api.GET('/api/spaces/{space_id}/epics', {
        params: { path: { space_id: spaceId }, query: { cursor, limit: 50 } },
      }),
    ),
  )

export function useEpics(spaceId: string) {
  return usePaged(epicsQuery(spaceId))
}
