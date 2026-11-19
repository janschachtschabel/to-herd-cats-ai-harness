import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { meQuery } from '@/features/auth/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

/** Every list and count of the people administration lives under this key. */
export const userKeys = {
  all: ['admin', 'users'] as const,
  pendingCount: ['admin', 'users', 'pending-count'] as const,
}

export const usersQuery = pagedQuery(['admin', 'users'], async (cursor) =>
  unwrap(await api.GET('/api/admin/users', { params: { query: { cursor } } })),
)

/** The self-registered accounts awaiting approval (plan M9 task 5b). */
export const pendingUsersQuery = pagedQuery(['admin', 'users', 'pending'], async (cursor) =>
  unwrap(await api.GET('/api/admin/users', { params: { query: { cursor, pending: true } } })),
)

export function usePendingUsers(enabled = true) {
  return usePaged({ ...pendingUsersQuery, enabled })
}

/** How many accounts wait for approval (the navigation's badge); only ask with
 *  `user.manage`. */
export function usePendingCount(enabled: boolean) {
  const query = useQuery({
    queryKey: userKeys.pendingCount,
    queryFn: async () => unwrap(await api.GET('/api/admin/users/pending/count')),
    enabled,
  })
  return query.data?.count ?? 0
}

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
    return queryClient.invalidateQueries({ queryKey: userKeys.all })
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

/** Turns the person's TOTP off (a lost device); audited by the server. */
export function useResetTotp() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: async (userId: string) =>
      unwrap(
        await api.POST('/api/admin/users/{user_id}/totp/reset', {
          params: { path: { user_id: userId } },
        }),
      ),
    onSuccess: () => invalidate(),
  })
}

/** Ends every session of the person (they stay active). */
export function useSignUserOut() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: async (userId: string) =>
      unwrap(
        await api.POST('/api/admin/users/{user_id}/sign-out', {
          params: { path: { user_id: userId } },
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

/** Approve (`approve`) or reject a waiting account, naming the version read. */
export function useDecideSignup() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: async ({ user, approve }: { user: Schemas['UserOut']; approve: boolean }) => {
      const options = {
        params: { path: { user_id: user.id } },
        body: { version: user.version },
      }
      return unwrap(
        approve
          ? await api.POST('/api/admin/users/{user_id}/approve', options)
          : await api.POST('/api/admin/users/{user_id}/reject', options),
      )
    },
    onSuccess: () => invalidate(),
  })
}
