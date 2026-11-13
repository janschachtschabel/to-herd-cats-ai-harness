import {
  type QueryClient,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { api, unwrap, type Schemas, type SpaceMember } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export const spacesQuery = pagedQuery(['spaces', 'list'], async (cursor) =>
  unwrap(await api.GET('/api/spaces', { params: { query: { cursor } } })),
)

/** The sidebar's list: like `spacesQuery`, without other people's personal spaces
 *  (the server leaves them out before paging, so no page is filled with them). */
export const sidebarSpacesQuery = pagedQuery(['spaces', 'sidebar'], async (cursor) =>
  unwrap(
    await api.GET('/api/spaces', {
      params: { query: { cursor, include_others_personal: false } },
    }),
  ),
)

export const spaceQuery = (spaceId: string) =>
  queryOptions({
    queryKey: ['spaces', 'detail', spaceId],
    queryFn: async () =>
      unwrap(await api.GET('/api/spaces/{space_id}', { params: { path: { space_id: spaceId } } })),
  })

export const spaceMembersQuery = (spaceId: string) =>
  pagedQuery(['spaces', 'members', spaceId], async (cursor) =>
    unwrap(
      await api.GET('/api/spaces/{space_id}/members', {
        params: { path: { space_id: spaceId }, query: { cursor } },
      }),
    ),
  )

/** Both lists (spaces page, sidebar) after a space was created or changed. */
function invalidateSpaceLists(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: spacesQuery.queryKey })
  void queryClient.invalidateQueries({ queryKey: sidebarSpacesQuery.queryKey })
}

export function useSpaces() {
  return usePaged(spacesQuery)
}

export function useSidebarSpaces() {
  return usePaged(sidebarSpacesQuery)
}

export function useSpace(spaceId: string) {
  return useQuery(spaceQuery(spaceId))
}

export function useSpaceMembers(spaceId: string) {
  return usePaged(spaceMembersQuery(spaceId))
}

export function useCreateSpace() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['SpaceCreate']) =>
      unwrap(await api.POST('/api/spaces', { body })),
    onSuccess: (space) => {
      queryClient.setQueryData(spaceQuery(space.id).queryKey, space)
      invalidateSpaceLists(queryClient)
    },
  })
}

export function useUpdateSpace(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['SpaceUpdateIn']) =>
      unwrap(
        await api.PATCH('/api/spaces/{space_id}', {
          params: { path: { space_id: spaceId } },
          body,
        }),
      ),
    onSuccess: (space) => {
      queryClient.setQueryData(spaceQuery(spaceId).queryKey, space)
      invalidateSpaceLists(queryClient)
    },
  })
}

export function useSetSpaceMember(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['SpaceMemberIn']) =>
      unwrap(
        await api.PUT('/api/spaces/{space_id}/members', {
          params: { path: { space_id: spaceId } },
          body,
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: spaceMembersQuery(spaceId).queryKey }),
  })
}

export function useRemoveSpaceMember(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (member: SpaceMember) =>
      unwrap(
        await api.DELETE('/api/spaces/{space_id}/members/{member_type}/{member_id}', {
          params: {
            path: {
              space_id: spaceId,
              member_type: member.member_type as 'user' | 'group',
              member_id: member.member_id,
            },
          },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: spaceMembersQuery(spaceId).queryKey }),
  })
}
