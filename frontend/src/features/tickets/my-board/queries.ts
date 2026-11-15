import {
  infiniteQueryOptions,
  queryOptions,
  useInfiniteQuery,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { spaceQuery } from '@/features/spaces/queries'
import { api, unwrap, type MyBoard, type MyCard, type SpaceRole } from '@/lib/api'
import type { StatusCategory } from '../display'
import { ticketKeys } from '../keys'
import { storeTicket } from '../queries'

const COLUMN_SIZE = 50

/** The columns of my board: the categories a person works through (cancelled tickets
 *  are not shown; done ones only from the last 14 days, as the server answers). */
export const MY_CATEGORIES: readonly StatusCategory[] = ['open', 'active', 'review', 'done']

export const myBoardQuery = queryOptions({
  queryKey: ticketKeys.myBoard,
  queryFn: async () =>
    unwrap(await api.GET('/api/tickets/my-board', { params: { query: { limit: COLUMN_SIZE } } })),
})

export function useMyBoard() {
  return useQuery(myBoardQuery)
}

/** The rest of a column, page by page, from the cursor of its first page. */
export function useMyColumnMore(category: StatusCategory, first: string | null, wanted: boolean) {
  const query = useInfiniteQuery({
    ...infiniteQueryOptions({
      queryKey: ticketKeys.myColumn(category),
      queryFn: async ({ pageParam }) =>
        unwrap(
          await api.GET('/api/tickets/my-board/{category}', {
            params: { path: { category }, query: { cursor: pageParam, limit: COLUMN_SIZE } },
          }),
        ),
      initialPageParam: first ?? '',
      getNextPageParam: (last: { next_cursor?: string | null }) => last.next_cursor ?? undefined,
    }),
    enabled: wanted && first !== null,
  })
  return {
    items: query.data?.pages.flatMap((page) => page.items) ?? [],
    hasMore: first !== null && (!query.data || query.hasNextPage),
    loading: query.isFetching,
    loadMore: () => void (query.data ? query.fetchNextPage() : query.refetch()),
  }
}

/** My role in each space my cards come from (to offer moves only where `ticket.edit`
 *  holds): one request per space, cached with the space. */
export function useSpaceRoles(spaceIds: string[]): Map<string, SpaceRole | null | undefined> {
  const results = useQueries({ queries: spaceIds.map((id) => spaceQuery(id)) })
  return new Map(spaceIds.map((id, i) => [id, results[i]?.data?.my_role]))
}

/** Moves a card into a category: the server sets the first status of that category in
 *  the ticket's own space, with the version the card was read at. At once on the board
 *  (optimistic); a refusal (409 changed meanwhile, 422 `ticket.category_empty`) puts it
 *  back and is the mutation's error. Dragging and the menu use this one. */
export function useMoveToCategory() {
  const queryClient = useQueryClient()
  const key = ticketKeys.myBoard
  return useMutation({
    mutationFn: async ({ ticket, category }: { ticket: MyCard; category: StatusCategory }) =>
      unwrap(
        await api.POST('/api/tickets/{number}/move-category', {
          params: { path: { number: ticket.number } },
          body: { category, version: ticket.version },
        }),
      ),
    onMutate: async ({ ticket, category }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const before = queryClient.getQueryData<MyBoard>(key)
      if (before) queryClient.setQueryData<MyBoard>(key, moveMyCard(before, ticket, category))
      return { before }
    },
    onError: (_error, _vars, context) => {
      if (context?.before) queryClient.setQueryData(key, context.before)
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
    },
    onSuccess: (updated) => storeTicket(queryClient, updated),
  })
}

/** The board with `ticket` moved to the column of `category` (on top), counts adjusted.
 *  Its status keeps its name until the server's answer names the new one. */
export function moveMyCard(board: MyBoard, ticket: MyCard, category: StatusCategory): MyBoard {
  if (ticket.status.category === category) return board
  if (!board.columns.some((column) => column.category === category)) return board
  const moved = { ...ticket, status: { ...ticket.status, category } }
  return {
    columns: board.columns.map((column) => {
      if (column.category === category) {
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
