import { useInfiniteQuery } from '@tanstack/react-query'
import { api, unwrap, type DirectoryEntry } from '@/lib/api'
import { pagedQuery } from '@/lib/paging'

export type DirectoryType = 'user' | 'group'

/** With `spaceId`: only the people who may read that space (never groups). */
export const directoryQuery = (q: string, type?: DirectoryType, spaceId?: string) =>
  pagedQuery(['directory', q, type ?? 'all', spaceId ?? 'org'], async (cursor) =>
    unwrap(
      await api.GET('/api/directory', {
        params: { query: { q, cursor, limit: 20, type, space_id: spaceId } },
      }),
    ),
  )

/** The key that names a principal in "present" sets: "type:id". */
export const principalKey = (entry: { type: string; id: string }) => `${entry.type}:${entry.id}`

/** People and groups (only people with `type: 'user'`) whose name contains `q`,
 *  without those in `exclude`; with `spaceId` only the people who may read that space.
 *  Fetched only while `enabled` (the picker is open). */
export function useDirectory(
  q: string,
  exclude: Set<string>,
  enabled: boolean,
  type?: DirectoryType,
  spaceId?: string,
) {
  const query = useInfiniteQuery({ ...directoryQuery(q, type, spaceId), enabled })
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
