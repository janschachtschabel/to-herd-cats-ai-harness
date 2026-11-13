import {
  type QueryClient,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { api, ApiError, unwrap, type Schemas, type TreeNode, type WikiPage } from '@/lib/api'

// The tree endpoint is paged (≤ 100 per request); the tree needs every page, so the
// pages are fetched one after the other, up to this many requests.
const TREE_PAGE_SIZE = 100
const MAX_TREE_REQUESTS = 50

export const wikiKeys = {
  all: ['wiki'] as const,
  tree: (spaceId: string) => ['wiki', 'tree', spaceId] as const,
  page: (pageId: string) => ['wiki', 'page', pageId] as const,
  byPath: (spaceId: string, path: string) => ['wiki', 'path', spaceId, path] as const,
}

export const treeQuery = (spaceId: string) =>
  queryOptions({
    queryKey: wikiKeys.tree(spaceId),
    queryFn: async (): Promise<TreeNode[]> => {
      const nodes: TreeNode[] = []
      let cursor: string | undefined
      for (let i = 0; i < MAX_TREE_REQUESTS; i++) {
        const batch = unwrap(
          await api.GET('/api/spaces/{space_id}/pages/tree', {
            params: { path: { space_id: spaceId }, query: { cursor, limit: TREE_PAGE_SIZE } },
          }),
        )
        nodes.push(...batch.items)
        cursor = batch.next_cursor ?? undefined
        if (!cursor) break
      }
      return nodes
    },
  })

export const pageByPathQuery = (spaceId: string, path: string) =>
  queryOptions({
    queryKey: wikiKeys.byPath(spaceId, path),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/pages/by-path', {
          params: { path: { space_id: spaceId }, query: { path } },
        }),
      ),
  })

export const pageQuery = (pageId: string) =>
  queryOptions({
    queryKey: wikiKeys.page(pageId),
    queryFn: async () =>
      unwrap(await api.GET('/api/pages/{page_id}', { params: { path: { page_id: pageId } } })),
  })

export function useTree(spaceId: string) {
  return useQuery(treeQuery(spaceId))
}

export function usePageByPath(spaceId: string, path: string) {
  return useQuery({ ...pageByPathQuery(spaceId, path), enabled: path !== '' })
}

/** A page the server answered with: stored under its id and its path. */
export function storePage(queryClient: QueryClient, page: WikiPage): void {
  queryClient.setQueryData(wikiKeys.page(page.id), page)
  queryClient.setQueryData(wikiKeys.byPath(page.space_id, page.path), page)
}

export function invalidateTree(queryClient: QueryClient, spaceId: string): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: wikiKeys.tree(spaceId) })
}

/** After a 409 version conflict the page is fetched again, so the next try uses the
 *  current version; the dialog tells the person (see `WikiError`). */
export function refetchOnConflict(queryClient: QueryClient, page: WikiPage, error: unknown) {
  if (error instanceof ApiError && error.isVersionConflict) {
    void queryClient.invalidateQueries({ queryKey: wikiKeys.page(page.id) })
    void queryClient.invalidateQueries({ queryKey: wikiKeys.byPath(page.space_id, page.path) })
  }
}

export function useCreatePage(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['PageCreate']) =>
      unwrap(
        await api.POST('/api/spaces/{space_id}/pages', {
          params: { path: { space_id: spaceId } },
          body,
        }),
      ),
    onSuccess: (page) => {
      storePage(queryClient, page)
      void invalidateTree(queryClient, spaceId)
    },
  })
}

/** Title, content or both; `version` is the page's version the edit started from. */
export function useUpdatePage(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['PageUpdate']) =>
      unwrap(
        await api.PATCH('/api/pages/{page_id}', {
          params: { path: { page_id: page.id } },
          body,
        }),
      ),
    onSuccess: (updated) => {
      storePage(queryClient, updated)
      if (updated.title !== page.title) void invalidateTree(queryClient, page.space_id)
    },
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

export function usePublishPage(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/pages/{page_id}/publish', {
          params: { path: { page_id: page.id } },
          body: { version: page.version },
        }),
      ),
    onSuccess: (updated) => {
      storePage(queryClient, updated)
      void invalidateTree(queryClient, page.space_id)
    },
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

export function useMovePage(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (target: { parent_id: string | null; position: number | null }) =>
      unwrap(
        await api.POST('/api/pages/{page_id}/move', {
          params: { path: { page_id: page.id } },
          body: { ...target, version: page.version },
        }),
      ),
    onSuccess: (moved) => {
      storePage(queryClient, moved)
      // Paths below the page changed too.
      void queryClient.invalidateQueries({ queryKey: ['wiki', 'path', page.space_id] })
      void invalidateTree(queryClient, page.space_id)
    },
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

/** Fetches the page as it is on the server now (after a conflict). */
export function useFetchLatestPage() {
  const queryClient = useQueryClient()
  return async (page: WikiPage): Promise<WikiPage> => {
    const latest = await queryClient.fetchQuery({ ...pageQuery(page.id), staleTime: 0 })
    storePage(queryClient, latest)
    return latest
  }
}
