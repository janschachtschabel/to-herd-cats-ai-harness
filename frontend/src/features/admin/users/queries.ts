import { useMutation, useQueryClient } from '@tanstack/react-query'
import { meQuery } from '@/features/auth/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export const usersQuery = pagedQuery(['admin', 'users'], async (cursor) =>
  unwrap(await api.GET('/api/admin/users', { params: { query: { cursor } } })),
)

/** Pass `enabled: false` where the caller may not list people. */
export function useUsers(enabled = true) {
  return usePaged({ ...usersQuery, enabled })
}

/** The list again; and `me` too when the change was to oneself (it moves one's version
 *  and may change one's name or language). */
function useInvalidateUsers() {
  const queryClient = useQueryClient()
  return (userId?: string) => {
    if (userId && queryClient.getQueryData(meQuery.queryKey)?.user.id === userId) {
      void queryClient.invalidateQueries({ queryKey: meQuery.queryKey, exact: true })
    }
    return queryClient.invalidateQueries({ queryKey: usersQuery.queryKey })
  }
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
    onSuccess: () => invalidate(userId),
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
