import {
  infiniteQueryOptions,
  queryOptions,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { api, unwrap, type Board, type Page, type TicketSummary } from '@/lib/api'
import type { TicketKind } from '../display'
import { ticketKeys } from '../keys'
import { storeTicket } from '../queries'

const COLUMN_SIZE = 50

/** The board's filters (plan M4, Task 5): mine only, one kind, one tag, one epic; and
 *  (plan M4b) one person (`me`, an id, `none`: nobody) and one sprint (an id, `none`:
 *  the backlog, `all`: chosen to be none, see `daily/logic.ts`). */
export interface BoardFilters {
  assignee?: string
  kind?: TicketKind
  tag?: string
  epic?: string
  sprint?: string
}

export function filterQuery(filters: BoardFilters) {
  return {
    assignee: filters.assignee,
    kind: filters.kind,
    tag: filters.tag ? [filters.tag] : undefined,
    epic: filters.epic,
    sprint: filters.sprint === 'all' ? undefined : filters.sprint,
  }
}

export const boardQuery = (spaceId: string, filters: BoardFilters) =>
  queryOptions({
    queryKey: ticketKeys.board(spaceId, filters),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/board', {
          params: {
            path: { space_id: spaceId },
            query: { ...filterQuery(filters), limit: COLUMN_SIZE },
          },
        }),
      ),
  })

export function useBoard(spaceId: string, filters: BoardFilters, enabled = true) {
  return useQuery({ ...boardQuery(spaceId, filters), enabled })
}

/** A column's tickets after its first page (the board's), loaded on request. */
const columnQuery = (spaceId: string, statusId: string, filters: BoardFilters, first: string) =>
  infiniteQueryOptions({
    queryKey: ticketKeys.column(spaceId, statusId, filters),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/board/{status_id}', {
          params: {
            path: { space_id: spaceId, status_id: statusId },
            query: { ...filterQuery(filters), cursor: pageParam, limit: COLUMN_SIZE },
          },
        }),
      ),
    initialPageParam: first,
    getNextPageParam: (last: Page<TicketSummary>) => last.next_cursor ?? undefined,
  })

/** The rest of a column, page by page, from the cursor of its first page. */
export function useColumnMore(
  spaceId: string,
  statusId: string,
  filters: BoardFilters,
  first: string | null,
  wanted: boolean,
) {
  const query = useInfiniteQuery({
    ...columnQuery(spaceId, statusId, filters, first ?? ''),
    enabled: wanted && first !== null,
  })
  return {
    items: query.data?.pages.flatMap((page) => page.items) ?? [],
    hasMore: first !== null && (!query.data || query.hasNextPage),
    loading: query.isFetching,
    loadMore: () => void (query.data ? query.fetchNextPage() : query.refetch()),
  }
}

/** Moves a card to another status: at once on the board (optimistic), with the version
 *  the card was read at; a refusal (409 "changed in the meantime", or any other) puts
 *  it back and the error is the mutation's. Dragging and the menu use this one. */
export function useMoveTicket(spaceId: string, filters: BoardFilters) {
  const queryClient = useQueryClient()
  const key = ticketKeys.board(spaceId, filters)
  return useMutation({
    mutationFn: async ({ ticket, statusId }: { ticket: TicketSummary; statusId: string }) =>
      unwrap(
        await api.PATCH('/api/tickets/{number}', {
          params: { path: { number: ticket.number } },
          body: { status_id: statusId, version: ticket.version },
        }),
      ),
    onMutate: async ({ ticket, statusId }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const before = queryClient.getQueryData<Board>(key)
      if (before) queryClient.setQueryData<Board>(key, moveCard(before, ticket, statusId))
      return { before }
    },
    onError: (_error, _vars, context) => {
      if (context?.before) queryClient.setQueryData(key, context.before)
      // Changed in the meantime (or gone): the board as it is now, with fresh versions.
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
    },
    onSuccess: (updated) => storeTicket(queryClient, updated),
  })
}

/** The board with `ticket` moved to the column of `statusId` (on top), counts adjusted. */
export function moveCard(board: Board, ticket: TicketSummary, statusId: string): Board {
  const target = board.columns.find((c) => c.status.id === statusId)
  if (!target || ticket.status.id === statusId) return board
  const moved = { ...ticket, status: target.status }
  return {
    columns: board.columns.map((column) => {
      if (column.status.id === statusId) {
        return { ...column, count: column.count + 1, items: [moved, ...column.items] }
      }
      if (column.items.some((item) => item.id === ticket.id)) {
        return {
          ...column,
          count: Math.max(0, column.count - 1),
          items: column.items.filter((item) => item.id !== ticket.id),
        }
      }
      return column
    }),
  }
}
