import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type OwnSession = Schemas['OwnSessionOut']

export const mySessionsQuery = pagedQuery(['auth', 'sessions'], async (cursor) =>
  unwrap(await api.GET('/api/auth/me/sessions', { params: { query: { cursor } } })),
)

/** The person's running sign-ins, newest first; `current` is this browser's. */
export function useMySessions() {
  return usePaged(mySessionsQuery)
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: mySessionsQuery.queryKey })
}

export function useEndSession() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async (sessionId: string) =>
      unwrap(
        await api.DELETE('/api/auth/me/sessions/{session_id}', {
          params: { path: { session_id: sessionId } },
        }),
      ),
    onSuccess: () => void refresh(),
  })
}

export function useSignOutOthers() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/auth/me/sessions/sign-out-others')),
    onSuccess: () => void refresh(),
  })
}
