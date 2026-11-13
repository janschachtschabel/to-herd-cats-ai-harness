import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type WikiPage } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { invalidateTree, refetchOnConflict, storePage, wikiKeys } from '../queries'

export const trashQuery = (spaceId: string) =>
  pagedQuery(['wiki', 'trash', spaceId], async (cursor) =>
    unwrap(
      await api.GET('/api/spaces/{space_id}/trash', {
        params: { path: { space_id: spaceId }, query: { cursor } },
      }),
    ),
  )

export function useTrashList(spaceId: string) {
  return usePaged(trashQuery(spaceId))
}

export function useTrashPage(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/pages/{page_id}/trash', {
          params: { path: { page_id: page.id } },
          body: { version: page.version },
        }),
      ),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: wikiKeys.page(page.id) })
      // Not refetched while the trashed page is still on screen (it would be a 404);
      // the next visit of any path loads it fresh.
      void queryClient.invalidateQueries({
        queryKey: ['wiki', 'path', page.space_id],
        refetchType: 'none',
      })
      void queryClient.invalidateQueries({ queryKey: trashQuery(page.space_id).queryKey })
      void invalidateTree(queryClient, page.space_id)
    },
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

export function useRestorePage(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (pageId: string) =>
      unwrap(
        await api.POST('/api/pages/{page_id}/restore', { params: { path: { page_id: pageId } } }),
      ),
    onSuccess: (page) => {
      storePage(queryClient, page)
      void queryClient.invalidateQueries({ queryKey: trashQuery(spaceId).queryKey })
      void invalidateTree(queryClient, spaceId)
    },
  })
}

export function usePurgePage(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (pageId: string) =>
      unwrap(await api.DELETE('/api/pages/{page_id}', { params: { path: { page_id: pageId } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trashQuery(spaceId).queryKey }),
  })
}
