import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Tag, type WikiPage } from '@/lib/api'
import { invalidateTree, refetchOnConflict, storePage } from '../queries'

const MAX_TAG_REQUESTS = 10

/** The tags usable in a space (system tags and the space's own), all pages of them. */
export const spaceTagsQuery = (spaceId: string) => ({
  queryKey: ['wiki', 'tags', spaceId] as const,
  queryFn: async (): Promise<Tag[]> => {
    const tags: Tag[] = []
    let cursor: string | undefined
    for (let i = 0; i < MAX_TAG_REQUESTS; i++) {
      const batch = unwrap(
        await api.GET('/api/tags', {
          params: { query: { space_id: spaceId, cursor, limit: 100 } },
        }),
      )
      tags.push(...batch.items)
      cursor = batch.next_cursor ?? undefined
      if (!cursor) break
    }
    return tags
  },
})

export function useSpaceTags(spaceId: string) {
  return useQuery(spaceTagsQuery(spaceId))
}

export function useSetPageTags(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (tagIds: string[]) =>
      unwrap(
        await api.PUT('/api/pages/{page_id}/tags', {
          params: { path: { page_id: page.id } },
          body: { tag_ids: tagIds, version: page.version },
        }),
      ),
    onSuccess: (updated) => {
      storePage(queryClient, updated)
      void invalidateTree(queryClient, page.space_id)
    },
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

/** A new tag of the space (needs page.moderate there). */
export function useCreateSpaceTag(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(await api.POST('/api/tags', { body: { name, space_id: spaceId } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: spaceTagsQuery(spaceId).queryKey }),
  })
}
