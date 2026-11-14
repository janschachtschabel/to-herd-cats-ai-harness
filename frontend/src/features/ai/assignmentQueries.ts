import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { meQuery } from '@/features/auth/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { aiKeys } from './keys'

/** Who uses which model (`ai.manage`): the standard and its version, which the
 *  ordered group list shares. */
export function useAssignments() {
  return useQuery({
    queryKey: aiKeys.assignments,
    queryFn: async () => unwrap(await api.GET('/api/ai/assignments')),
  })
}

export const groupAssignmentsQuery = pagedQuery(aiKeys.groupAssignments, async (cursor) =>
  unwrap(
    await api.GET('/api/ai/assignments/groups', { params: { query: { cursor, limit: 100 } } }),
  ),
)

export function useGroupAssignments() {
  return usePaged(groupAssignmentsQuery)
}

export const userAssignmentsQuery = pagedQuery(aiKeys.userAssignments, async (cursor) =>
  unwrap(await api.GET('/api/ai/assignments/users', { params: { query: { cursor } } })),
)

export function useUserAssignments() {
  return usePaged(userAssignmentsQuery)
}

/** After any change: the lists, and my own `ai.use` (I may have gained or lost it). */
function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: aiKeys.assignments })
    void queryClient.invalidateQueries({ queryKey: meQuery.queryKey })
  }
}

export function useSetDefault() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async (body: Schemas['DefaultIn']) =>
      unwrap(await api.PUT('/api/ai/assignments/default', { body })),
    onSuccess: refresh,
  })
}

export function useSetGroups() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async (body: Schemas['GroupsIn']) =>
      unwrap(await api.PUT('/api/ai/assignments/groups', { body })),
    onSuccess: refresh,
  })
}

export function useSetUserAssignment() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async ({ userId, body }: { userId: string; body: Schemas['UserAssignmentIn'] }) =>
      unwrap(
        await api.PUT('/api/ai/assignments/users/{user_id}', {
          params: { path: { user_id: userId } },
          body,
        }),
      ),
    onSuccess: refresh,
  })
}

export function useRemoveUserAssignment() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async ({ userId, version }: { userId: string; version: number }) =>
      unwrap(
        await api.DELETE('/api/ai/assignments/users/{user_id}', {
          params: { path: { user_id: userId }, query: { version } },
        }),
      ),
    onSuccess: refresh,
  })
}
