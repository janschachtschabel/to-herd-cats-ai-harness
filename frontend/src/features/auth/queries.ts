import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Me, type Permission, type Schemas } from '@/lib/api'
import { runBeforeLogout } from '@/lib/beforeLogout'

export const meQuery = queryOptions({
  queryKey: ['auth', 'me'],
  queryFn: async (): Promise<Me | null> => {
    const result = await api.GET('/api/auth/me')
    if (result.response.status === 401) return null
    return unwrap(result)
  },
  staleTime: 60_000,
})

/** The person logged in, or null. */
export function useMe(): Me | null {
  return useQuery(meQuery).data ?? null
}

/** Whether `me` holds a system-wide right; what the UI shows depends on nothing else. */
export function hasPermission(me: Me | null | undefined, permission: Permission): boolean {
  return me?.permissions.includes(permission) ?? false
}

export function usePermission(permission: Permission): boolean {
  return hasPermission(useMe(), permission)
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) =>
      unwrap(await api.POST('/api/auth/login', { body })),
    onSuccess: (me) => {
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'auth' })
      queryClient.setQueryData(meQuery.queryKey, me)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await runBeforeLogout()
      await api.POST('/api/auth/logout')
    },
    onSettled: () => {
      queryClient.setQueryData(meQuery.queryKey, null)
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'auth' })
    },
  })
}

export type SignInProvider = Schemas['PublicProviderOut']

/** The providers to offer on the sign-in page (no session needed); none on failure. */
export const providersQuery = queryOptions({
  queryKey: ['auth', 'providers'],
  queryFn: async (): Promise<SignInProvider[]> =>
    unwrap(await api.GET('/api/auth/providers', { params: { query: { limit: 100 } } })).items,
  staleTime: 60_000,
  retry: false,
})

export function useSignInProviders(): SignInProvider[] {
  return useQuery(providersQuery).data ?? []
}

/** Where a provider's sign-in starts: a full page load (the API redirects to it). */
export function signInHref(key: string): string {
  return `/api/auth/oidc/${encodeURIComponent(key)}/start`
}
