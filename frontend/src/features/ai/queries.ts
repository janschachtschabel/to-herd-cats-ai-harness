import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { aiKeys } from './keys'

/** The AI connections (`ai.manage`); everyone else gets 404 and never asks. */
export const connectionsQuery = pagedQuery(aiKeys.connections, async (cursor) =>
  unwrap(await api.GET('/api/ai/connections', { params: { query: { cursor, limit: 100 } } })),
)

export const connectionQuery = (connectionId: string) =>
  queryOptions({
    queryKey: aiKeys.connection(connectionId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/ai/connections/{connection_id}', {
          params: { path: { connection_id: connectionId } },
        }),
      ),
  })

/** Pass `enabled: false` where the caller may not list connections. */
export function useConnections(enabled = true) {
  return usePaged({ ...connectionsQuery, enabled })
}

function useRefreshConnections() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: aiKeys.connections })
    // Assignments name the connection; a renamed or disabled one shows there too.
    void queryClient.invalidateQueries({ queryKey: aiKeys.assignments })
  }
}

/** A mutation that may carry a typed key: dropped from the cache once it has no
 *  observer, so the key does not stay in memory (TanStack keeps variables 5 min). */
const FORGET_VARIABLES = { gcTime: 0 } as const

export function useCreateConnection() {
  const refresh = useRefreshConnections()
  return useMutation({
    ...FORGET_VARIABLES,
    mutationFn: async (body: Schemas['ConnectionCreate']) =>
      unwrap(await api.POST('/api/ai/connections', { body })),
    onSuccess: refresh,
  })
}

export function useUpdateConnection(connectionId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshConnections()
  return useMutation({
    ...FORGET_VARIABLES,
    mutationFn: async (body: Schemas['ConnectionUpdate']) =>
      unwrap(
        await api.PATCH('/api/ai/connections/{connection_id}', {
          params: { path: { connection_id: connectionId } },
          body,
        }),
      ),
    onSuccess: (connection) => {
      queryClient.setQueryData(connectionQuery(connectionId).queryKey, connection)
      refresh()
    },
  })
}

export function useDeleteConnection() {
  const refresh = useRefreshConnections()
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.DELETE('/api/ai/connections/{connection_id}', {
          params: { path: { connection_id: id }, query: { version } },
        }),
      ),
    onSuccess: refresh,
  })
}

/** One small call to the provider; the answer is a state, never the provider's text. */
export function useTestConnection(connectionId: string) {
  return useMutation({
    mutationFn: async (model: string | null) =>
      unwrap(
        await api.POST('/api/ai/connections/{connection_id}/test', {
          params: { path: { connection_id: connectionId } },
          body: { model },
        }),
      ),
  })
}

/** Reads the provider's model list into the connection (the standard model stays first). */
export function useFetchModels(connectionId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshConnections()
  return useMutation({
    mutationFn: async (version: number) =>
      unwrap(
        await api.POST('/api/ai/connections/{connection_id}/models', {
          params: { path: { connection_id: connectionId } },
          body: { version },
        }),
      ),
    onSuccess: (connection) => {
      queryClient.setQueryData(connectionQuery(connectionId).queryKey, connection)
      refresh()
    },
  })
}

export function useConnection(connectionId: string) {
  return useQuery(connectionQuery(connectionId))
}
