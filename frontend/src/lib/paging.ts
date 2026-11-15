import { infiniteQueryOptions, useInfiniteQuery, type QueryKey } from '@tanstack/react-query'
import type { Page } from './api'

/** Query options for a cursor-paged list endpoint ("Mehr laden"). */
export function pagedQuery<T>(
  queryKey: QueryKey,
  fetchPage: (cursor: string | undefined) => Promise<Page<T>>,
) {
  return infiniteQueryOptions({
    queryKey,
    queryFn: ({ pageParam }) => fetchPage(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: Page<T>) => last.next_cursor ?? undefined,
  })
}

/** A paged list with its loaded items flattened. */
export function usePaged<T>(options: ReturnType<typeof pagedQuery<T>>) {
  const query = useInfiniteQuery(options)
  const items: T[] = query.data?.pages.flatMap((page) => page.items) ?? []
  return {
    items,
    isPending: query.isPending,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    hasMore: query.hasNextPage,
    loadingMore: query.isFetchingNextPage,
    loadMore: () => void query.fetchNextPage(),
  }
}
