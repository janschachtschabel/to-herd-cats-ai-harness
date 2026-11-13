import { type QueryClient, useMutation, useQueryClient } from '@tanstack/react-query'
import { spaceTagsQuery } from '@/features/wiki/tags/queries'
import { api, unwrap, type Page, type Schemas, type Tag } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

/** The system-wide tags only (`?system=true`), paged ("Mehr laden"). */
export const systemTagsQuery = pagedQuery(['tags', 'system'], async (cursor) =>
  unwrap(await api.GET('/api/tags', { params: { query: { system: true, cursor } } })),
)

export function useSystemTags() {
  return usePaged(systemTagsQuery)
}

/** Where a tag lives: system-wide (`null`) or in a space. */
export type TagScope = string | null

/** Every list that shows tags: the system list, each space's list, and the tree (a
 *  deleted tag leaves the pages it was on). */
function refreshTags(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: systemTagsQuery.queryKey })
  void queryClient.invalidateQueries({ queryKey: ['wiki', 'tags'] })
  void queryClient.invalidateQueries({ queryKey: ['wiki', 'tree'] })
}

/** The tag as the server has it now (after a version conflict), read from its list. */
export async function freshTag(
  queryClient: QueryClient,
  scope: TagScope,
  tagId: string,
): Promise<Tag | undefined> {
  if (scope === null) {
    await queryClient.refetchQueries({ queryKey: systemTagsQuery.queryKey })
    const data = queryClient.getQueryData<{ pages: Page<Tag>[] }>(systemTagsQuery.queryKey)
    return data?.pages.flatMap((p) => p.items).find((tag) => tag.id === tagId)
  }
  const tags = await queryClient.fetchQuery({ ...spaceTagsQuery(scope), staleTime: 0 })
  return tags.find((tag) => tag.id === tagId)
}

export function useCreateTag(scope: TagScope) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Omit<Schemas['TagCreate'], 'space_id'>) =>
      unwrap(
        await api.POST('/api/tags', {
          body: scope === null ? body : { ...body, space_id: scope },
        }),
      ),
    onSuccess: () => refreshTags(queryClient),
  })
}

export function useUpdateTag(tagId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['TagUpdate']) =>
      unwrap(await api.PATCH('/api/tags/{tag_id}', { params: { path: { tag_id: tagId } }, body })),
    onSuccess: () => refreshTags(queryClient),
  })
}

export function useDeleteTag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (tagId: string) =>
      unwrap(await api.DELETE('/api/tags/{tag_id}', { params: { path: { tag_id: tagId } } })),
    onSuccess: () => refreshTags(queryClient),
  })
}
