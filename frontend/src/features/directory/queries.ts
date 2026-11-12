import { useInfiniteQuery } from '@tanstack/react-query'
import { api, unwrap, type DirectoryEntry } from '@/lib/api'
import { pagedQuery } from '@/lib/paging'

export const directoryQuery = (q: string) =>
  pagedQuery(['directory', q], async (cursor) =>
    unwrap(await api.GET('/api/directory', { params: { query: { q, cursor, limit: 20 } } })),
  )

/** The key that names a principal in "present" sets: "type:id". */
export const principalKey = (entry: { type: string; id: string }) => `${entry.type}:${entry.id}`

/** People and groups whose name (or email start) matches `q`, without those in `exclude`.
 *  Fetched only while `enabled` (the picker is open). */
export function useDirectory(q: string, exclude: Set<string>, enabled: boolean) {
  const query = useInfiniteQuery({ ...directoryQuery(q), enabled })
  const all: DirectoryEntry[] = query.data?.pages.flatMap((page) => page.items) ?? []
  return {
    items: all.filter((entry) => !exclude.has(principalKey(entry))),
    isPending: query.isPending,
    isError: query.isError,
    error: query.error,
    hasMore: query.hasNextPage,
    loadingMore: query.isFetchingNextPage,
    loadMore: () => void query.fetchNextPage(),
  }
}
