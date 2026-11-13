import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type WikiPage } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { refetchOnConflict, storePage } from '../queries'

export const versionsQuery = (pageId: string) =>
  pagedQuery(['wiki', 'versions', pageId], async (cursor) =>
    unwrap(
      await api.GET('/api/pages/{page_id}/versions', {
        params: { path: { page_id: pageId }, query: { cursor } },
      }),
    ),
  )

export function useVersions(pageId: string) {
  return usePaged(versionsQuery(pageId))
}

export function useVersion(pageId: string, number: number | null) {
  return useQuery({
    queryKey: ['wiki', 'version', pageId, number],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/pages/{page_id}/versions/{number}', {
          params: { path: { page_id: pageId, number: number ?? 0 } },
        }),
      ),
    enabled: number !== null,
  })
}

export const diffQuery = (pageId: string, from: number, to: number) =>
  queryOptions({
    queryKey: ['wiki', 'diff', pageId, from, to],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/pages/{page_id}/diff', {
          params: { path: { page_id: pageId }, query: { from, to } },
        }),
      ),
  })

export function useDiff(pageId: string, pair: { from: number; to: number } | null) {
  return useQuery({ ...diffQuery(pageId, pair?.from ?? 0, pair?.to ?? 0), enabled: !!pair })
}

export function useRestoreVersion(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (number: number) =>
      unwrap(
        await api.POST('/api/pages/{page_id}/versions/{number}/restore', {
          params: { path: { page_id: page.id, number } },
          body: { version: page.version },
        }),
      ),
    onSuccess: (restored) => {
      storePage(queryClient, restored)
      void queryClient.invalidateQueries({ queryKey: versionsQuery(page.id).queryKey })
    },
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

export function useLabelVersion(pageId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ number, label }: { number: number; label: string | null }) =>
      unwrap(
        await api.PATCH('/api/pages/{page_id}/versions/{number}', {
          params: { path: { page_id: pageId, number } },
          body: { label },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: versionsQuery(pageId).queryKey }),
  })
}
