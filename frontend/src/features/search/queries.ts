import { useInfiniteQuery } from '@tanstack/react-query'
import { api, unwrap, type MessageHit, type SearchHit } from '@/lib/api'

const PAGE_SIZE = 20

export type AnyHit = SearchHit | MessageHit

/** Full-text search over the pages and messages one may read (the server filters by
 *  rights, one ranking for both); nothing is asked while `q` is blank. */
export function useSearch(q: string, spaceId: string | null) {
  const query = useInfiniteQuery({
    queryKey: ['search', q, spaceId],
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/search', {
          params: {
            query: {
              q,
              space_id: spaceId ?? undefined,
              cursor: pageParam,
              limit: PAGE_SIZE,
            },
          },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: q.trim() !== '',
  })
  const items: AnyHit[] = query.data?.pages.flatMap((page) => page.items) ?? []
  return {
    items,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    hasMore: query.hasNextPage,
    loadMore: () => void query.fetchNextPage(),
  }
}
