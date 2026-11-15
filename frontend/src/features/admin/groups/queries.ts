import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export const groupsQuery = pagedQuery(['admin', 'groups', 'list'], async (cursor) =>
  unwrap(await api.GET('/api/admin/groups', { params: { query: { cursor } } })),
)

export const groupQuery = (groupId: string) =>
  queryOptions({
    queryKey: ['admin', 'groups', 'detail', groupId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/admin/groups/{group_id}', { params: { path: { group_id: groupId } } }),
      ),
  })

export const groupMembersQuery = (groupId: string) =>
  pagedQuery(['admin', 'groups', 'members', groupId], async (cursor) =>
    unwrap(
      await api.GET('/api/admin/groups/{group_id}/members', {
        params: { path: { group_id: groupId }, query: { cursor } },
      }),
    ),
  )

/** Pass `enabled: false` where the caller may not list groups. */
export function useGroups(enabled = true) {
  return usePaged({ ...groupsQuery, enabled })
}

export function useGroup(groupId: string) {
  return useQuery(groupQuery(groupId))
}

export function useGroupMembers(groupId: string) {
  return usePaged(groupMembersQuery(groupId))
}

export function useCreateGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['GroupCreate']) =>
      unwrap(await api.POST('/api/admin/groups', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: groupsQuery.queryKey }),
  })
}

export function useUpdateGroup(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['GroupUpdateIn']) =>
      unwrap(
        await api.PATCH('/api/admin/groups/{group_id}', {
          params: { path: { group_id: groupId } },
          body,
        }),
      ),
    onSuccess: (group) => {
      queryClient.setQueryData(groupQuery(groupId).queryKey, group)
      void queryClient.invalidateQueries({ queryKey: groupsQuery.queryKey })
    },
  })
}

export function useDeleteGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (groupId: string) =>
      unwrap(
        await api.DELETE('/api/admin/groups/{group_id}', {
          params: { path: { group_id: groupId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: groupsQuery.queryKey }),
  })
}

export function useAddGroupMember(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) =>
      unwrap(
        await api.POST('/api/admin/groups/{group_id}/members', {
          params: { path: { group_id: groupId } },
          body: { member_type: 'user', member_id: userId },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: groupMembersQuery(groupId).queryKey }),
  })
}

export function useRemoveGroupMember(groupId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) =>
      unwrap(
        await api.DELETE('/api/admin/groups/{group_id}/members/{member_type}/{member_id}', {
          params: { path: { group_id: groupId, member_type: 'user', member_id: userId } },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: groupMembersQuery(groupId).queryKey }),
  })
}
