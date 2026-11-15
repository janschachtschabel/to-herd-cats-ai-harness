import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type Identity = Schemas['IdentityOut']

export const myIdentitiesQuery = pagedQuery(['auth', 'identities'], async (cursor) =>
  unwrap(await api.GET('/api/auth/me/identities', { params: { query: { cursor } } })),
)

export function useMyIdentities() {
  return usePaged(myIdentitiesQuery)
}

export function useUnlinkMine() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (identityId: string) =>
      unwrap(
        await api.DELETE('/api/auth/me/identities/{identity_id}', {
          params: { path: { identity_id: identityId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: myIdentitiesQuery.queryKey }),
  })
}

/** Start linking an account at the provider: the browser then leaves for its page. */
export function useStartLink() {
  return useMutation({
    mutationFn: async (key: string) =>
      unwrap(await api.POST('/api/auth/me/identities/{key}/link', { params: { path: { key } } })),
    onSuccess: ({ url }) => window.location.assign(url),
  })
}
