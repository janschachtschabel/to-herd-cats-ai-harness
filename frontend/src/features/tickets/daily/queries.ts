import { queryOptions, useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api'
import { type BoardFilters, filterQuery } from '../board/queries'
import { ticketKeys } from '../keys'

const CELL_SIZE = 20

/** The daily view of a space's board: a row per person (and one for nobody), a cell
 *  per status with its count, how many changed since the last working day, and its
 *  first cards. Under the board's key, so every board refresh reaches it. */
export const dailyQuery = (spaceId: string, filters: BoardFilters) =>
  queryOptions({
    queryKey: ticketKeys.board(spaceId, { ...filters, group_by: 'assignee' }),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/board', {
          params: {
            path: { space_id: spaceId },
            query: { ...filterQuery(filters), group_by: 'assignee', limit: CELL_SIZE },
          },
        }),
      ),
  })

export function useDaily(spaceId: string, filters: BoardFilters) {
  return useQuery(dailyQuery(spaceId, filters))
}
