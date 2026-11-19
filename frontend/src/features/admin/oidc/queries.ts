import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { providersQuery } from '@/features/auth/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type OidcProvider = Schemas['ProviderOut']

export const oidcProvidersQuery = pagedQuery(['admin', 'oidc-providers'], async (cursor) =>
  unwrap(await api.GET('/api/admin/oidc-providers', { params: { query: { cursor } } })),
)

/** One provider, read fresh after a 409 to take its new version. */
export const oidcProviderQuery = (providerId: string) =>
  queryOptions({
    queryKey: ['admin', 'oidc-providers', providerId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/admin/oidc-providers/{provider_id}', {
          params: { path: { provider_id: providerId } },
        }),
      ),
  })

export function useOidcProviders() {
  return usePaged(oidcProvidersQuery)
}

/** The admin list and the sign-in page's buttons both follow a change. */
function useInvalidate() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: oidcProvidersQuery.queryKey }),
      queryClient.invalidateQueries({ queryKey: providersQuery.queryKey }),
    ])
}

export function useCreateOidcProvider() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (body: Schemas['ProviderCreate']) =>
      unwrap(await api.POST('/api/admin/oidc-providers', { body })),
    onSuccess: () => invalidate(),
  })
}

export function useUpdateOidcProvider(providerId: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (body: Schemas['ProviderUpdate']) =>
      unwrap(
        await api.PATCH('/api/admin/oidc-providers/{provider_id}', {
          params: { path: { provider_id: providerId } },
          body,
        }),
      ),
    onSuccess: () => invalidate(),
  })
}

export function useDeleteOidcProvider() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (provider: OidcProvider) =>
      unwrap(
        await api.DELETE('/api/admin/oidc-providers/{provider_id}', {
          params: { path: { provider_id: provider.id }, query: { version: provider.version } },
        }),
      ),
    onSuccess: () => invalidate(),
  })
}

export function useCheckOidcProvider() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (providerId: string) =>
      unwrap(
        await api.POST('/api/admin/oidc-providers/{provider_id}/check', {
          params: { path: { provider_id: providerId } },
        }),
      ),
    onSuccess: () => invalidate(),
  })
}

export const userIdentitiesQuery = (userId: string) =>
  pagedQuery(['admin', 'users', userId, 'identities'], async (cursor) =>
    unwrap(
      await api.GET('/api/admin/users/{user_id}/identities', {
        params: { path: { user_id: userId }, query: { cursor } },
      }),
    ),
  )

export function useUserIdentities(userId: string) {
  return usePaged(userIdentitiesQuery(userId))
}

export function useUnlinkUserIdentity(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (identityId: string) =>
      unwrap(
        await api.DELETE('/api/admin/users/{user_id}/identities/{identity_id}', {
          params: { path: { user_id: userId, identity_id: identityId } },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: userIdentitiesQuery(userId).queryKey }),
  })
}
