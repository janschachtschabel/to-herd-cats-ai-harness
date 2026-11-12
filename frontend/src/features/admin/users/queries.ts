import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export const usersQuery = pagedQuery(['admin', 'users'], async (cursor) =>
  unwrap(await api.GET('/api/admin/users', { params: { query: { cursor } } })),
)

/** Pass `enabled: false` where the caller may not list people. */
export function useUsers(enabled = true) {
  return usePaged({ ...usersQuery, enabled })
}

function useInvalidateUsers() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: usersQuery.queryKey })
}

export function useCreateUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: async (body: Schemas['UserCreate']) =>
      unwrap(await api.POST('/api/admin/users', { body })),
    onSuccess: () => invalidate(),
  })
}

export function useUpdateUser(userId: string) {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: async (body: Schemas['UserUpdateIn']) =>
      unwrap(
        await api.PATCH('/api/admin/users/{user_id}', {
          params: { path: { user_id: userId } },
          body,
        }),
      ),
    onSuccess: () => invalidate(),
  })
}

export function useSetUserActive() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: async ({ userId, active }: { userId: string; active: boolean }) => {
      const params = { params: { path: { user_id: userId } } }
      return unwrap(
        active
          ? await api.POST('/api/admin/users/{user_id}/reactivate', params)
          : await api.POST('/api/admin/users/{user_id}/deactivate', params),
      )
    },
    onSuccess: () => invalidate(),
  })
}
