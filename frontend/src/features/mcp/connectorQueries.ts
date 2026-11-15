import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { mcpKeys } from './keys'

/**
 * Connectors: shared ones (`ai.manage`, `/api/ai/connectors`) and one's own
 * (`ai.use`, `/api/ai/my-connectors`), with the same routes. A secret is only ever
 * written; a mutation that carries one forgets its variables at once.
 */
export type ConnectorScope = 'shared' | 'personal'

const BASE = { shared: '/api/ai/connectors', personal: '/api/ai/my-connectors' } as const
const ONE = {
  shared: '/api/ai/connectors/{connector_id}',
  personal: '/api/ai/my-connectors/{connector_id}',
} as const
const AUTHORIZE = {
  shared: '/api/ai/connectors/{connector_id}/authorize',
  personal: '/api/ai/my-connectors/{connector_id}/authorize',
} as const
const DISCONNECT = {
  shared: '/api/ai/connectors/{connector_id}/disconnect',
  personal: '/api/ai/my-connectors/{connector_id}/disconnect',
} as const

const listKey = (scope: ConnectorScope) =>
  scope === 'shared' ? mcpKeys.connectors : mcpKeys.myConnectors

const FORGET_VARIABLES = { gcTime: 0 } as const

export function useConnectors(scope: ConnectorScope, enabled = true) {
  return usePaged({
    ...pagedQuery(listKey(scope), async (cursor) =>
      unwrap(await api.GET(BASE[scope], { params: { query: { cursor, limit: 100 } } })),
    ),
    enabled,
  })
}

/** One shared connector (a server's access, shown on the server's page). */
export const connectorQuery = (connectorId: string) =>
  queryOptions({
    queryKey: mcpKeys.connector(connectorId),
    queryFn: async () =>
      unwrap(await api.GET(ONE.shared, { params: { path: { connector_id: connectorId } } })),
  })

export function useConnector(connectorId: string | null) {
  return useQuery({ ...connectorQuery(connectorId ?? ''), enabled: connectorId !== null })
}

function useRefreshConnectors(scope: ConnectorScope) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: listKey(scope) })
    if (scope === 'shared') {
      void queryClient.invalidateQueries({ queryKey: mcpKeys.connectors })
    } else {
      void queryClient.invalidateQueries({ queryKey: mcpKeys.myServers })
    }
  }
}

export function useCreateConnector(scope: ConnectorScope) {
  const refresh = useRefreshConnectors(scope)
  return useMutation({
    ...FORGET_VARIABLES,
    mutationFn: async (body: Schemas['ConnectorCreate']) =>
      unwrap(await api.POST(BASE[scope], { body })),
    onSuccess: refresh,
  })
}

export function useUpdateConnector(scope: ConnectorScope, connectorId: string) {
  const refresh = useRefreshConnectors(scope)
  return useMutation({
    ...FORGET_VARIABLES,
    mutationFn: async (body: Schemas['ConnectorUpdate']) =>
      unwrap(
        await api.PATCH(ONE[scope], { params: { path: { connector_id: connectorId } }, body }),
      ),
    onSuccess: refresh,
  })
}

export function useDeleteConnector(scope: ConnectorScope) {
  const refresh = useRefreshConnectors(scope)
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.DELETE(ONE[scope], {
          params: { path: { connector_id: id }, query: { version } },
        }),
      ),
    onSuccess: refresh,
  })
}

/** Asks for the provider's sign-in address; the caller sends the browser there. */
export function useAuthorizeConnector(scope: ConnectorScope) {
  return useMutation({
    mutationFn: async (connectorId: string) =>
      unwrap(await api.POST(AUTHORIZE[scope], { params: { path: { connector_id: connectorId } } })),
  })
}

/** Drops an OAuth connector's tokens (the provider is told after the commit). */
export function useDisconnectConnector(scope: ConnectorScope) {
  const refresh = useRefreshConnectors(scope)
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.POST(DISCONNECT[scope], {
          params: { path: { connector_id: id } },
          body: { version },
        }),
      ),
    onSuccess: refresh,
  })
}

/** The enabled servers that act in each person's name, and whether I connected mine. */
export function useMyServers(enabled = true) {
  return usePaged({
    ...pagedQuery(mcpKeys.myServers, async (cursor) =>
      unwrap(
        await api.GET('/api/ai/my-mcp-servers', { params: { query: { cursor, limit: 100 } } }),
      ),
    ),
    enabled,
  })
}

/** The OAuth apps registered with providers (`ai.manage`). */
export function useOAuthClients(enabled = true) {
  return usePaged({
    ...pagedQuery(mcpKeys.clients, async (cursor) =>
      unwrap(await api.GET('/api/ai/oauth-clients', { params: { query: { cursor, limit: 100 } } })),
    ),
    enabled,
  })
}

function useRefreshClients() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: mcpKeys.clients })
}

export function useCreateClient() {
  const refresh = useRefreshClients()
  return useMutation({
    ...FORGET_VARIABLES,
    mutationFn: async (body: Schemas['ClientCreate']) =>
      unwrap(await api.POST('/api/ai/oauth-clients', { body })),
    onSuccess: refresh,
  })
}

export function useUpdateClient(clientId: string) {
  const refresh = useRefreshClients()
  return useMutation({
    ...FORGET_VARIABLES,
    mutationFn: async (body: Schemas['ClientUpdate']) =>
      unwrap(
        await api.PATCH('/api/ai/oauth-clients/{client_id}', {
          params: { path: { client_id: clientId } },
          body,
        }),
      ),
    onSuccess: refresh,
  })
}

export function useDeleteClient() {
  const refresh = useRefreshClients()
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.DELETE('/api/ai/oauth-clients/{client_id}', {
          params: { path: { client_id: id }, query: { version } },
        }),
      ),
    onSuccess: refresh,
  })
}

/** Reads a server's OAuth metadata to fill the form (a proposal, nothing stored). */
export function useDiscoverClient() {
  return useMutation({
    mutationFn: async (url: string) =>
      unwrap(await api.POST('/api/ai/oauth-clients/discover', { body: { url } })),
  })
}
