import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { mcpKeys } from './keys'

/** External MCP servers and their tools (`ai.manage`; everyone else gets 404). */
export const serversQuery = pagedQuery(mcpKeys.servers, async (cursor) =>
  unwrap(await api.GET('/api/ai/mcp-servers', { params: { query: { cursor, limit: 100 } } })),
)

export function useServers(enabled = true) {
  return usePaged({ ...serversQuery, enabled })
}

export const serverQuery = (serverId: string) =>
  queryOptions({
    queryKey: mcpKeys.server(serverId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/ai/mcp-servers/{server_id}', {
          params: { path: { server_id: serverId } },
        }),
      ),
  })

export function useServer(serverId: string) {
  return useQuery(serverQuery(serverId))
}

const toolsQuery = (serverId: string) =>
  pagedQuery(mcpKeys.tools(serverId), async (cursor) =>
    unwrap(
      await api.GET('/api/ai/mcp-servers/{server_id}/tools', {
        params: { path: { server_id: serverId }, query: { cursor, limit: 100 } },
      }),
    ),
  )

export function useServerTools(serverId: string) {
  return usePaged(toolsQuery(serverId))
}

/** After a change to servers or tools: the lists, the server, and every agent's grants
 *  (they list the organisation's usable external tools). */
function useRefreshServers() {
  const queryClient = useQueryClient()
  return (serverId?: string) => {
    void queryClient.invalidateQueries({ queryKey: mcpKeys.servers })
    if (serverId) void queryClient.invalidateQueries({ queryKey: mcpKeys.server(serverId) })
    void queryClient.invalidateQueries({ queryKey: mcpKeys.myServers })
    void queryClient.invalidateQueries({ queryKey: ['agents', 'detail'] })
  }
}

export function useCreateServer() {
  const refresh = useRefreshServers()
  return useMutation({
    mutationFn: async (body: Schemas['ServerCreate']) =>
      unwrap(await api.POST('/api/ai/mcp-servers', { body })),
    onSuccess: () => refresh(),
  })
}

export function useUpdateServer(serverId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshServers()
  return useMutation({
    mutationFn: async (body: Schemas['ServerUpdate']) =>
      unwrap(
        await api.PATCH('/api/ai/mcp-servers/{server_id}', {
          params: { path: { server_id: serverId } },
          body,
        }),
      ),
    onSuccess: (server) => {
      queryClient.setQueryData(serverQuery(serverId).queryKey, server)
      refresh(serverId)
    },
  })
}

export function useDeleteServer() {
  const refresh = useRefreshServers()
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.DELETE('/api/ai/mcp-servers/{server_id}', {
          params: { path: { server_id: id }, query: { version } },
        }),
      ),
    onSuccess: () => refresh(),
  })
}

/** Reads the server's tool list again: new tools come in pending, changed ones lose
 *  their approval, vanished ones are marked missing. */
export function useRefreshTools(serverId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshServers()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/ai/mcp-servers/{server_id}/refresh', {
          params: { path: { server_id: serverId } },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: mcpKeys.tools(serverId) })
      refresh(serverId)
    },
  })
}

/** One connection test; stores nothing. */
export function useTestServer(serverId: string) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/ai/mcp-servers/{server_id}/test', {
          params: { path: { server_id: serverId } },
        }),
      ),
  })
}

type ToolChange =
  | { action: 'approve' | 'block'; version: number }
  | { action: 'classify'; body: Schemas['ToolClassify'] }

/** Approve, block or classify one tool (with its version; 409 on a stale one). */
export function useChangeTool(serverId: string, toolId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshServers()
  const path = { server_id: serverId, tool_id: toolId }
  return useMutation({
    mutationFn: async (change: ToolChange) => {
      if (change.action === 'classify') {
        return unwrap(
          await api.PATCH('/api/ai/mcp-servers/{server_id}/tools/{tool_id}', {
            params: { path },
            body: change.body,
          }),
        )
      }
      const body = { version: change.version }
      return unwrap(
        change.action === 'approve'
          ? await api.POST('/api/ai/mcp-servers/{server_id}/tools/{tool_id}/approve', {
              params: { path },
              body,
            })
          : await api.POST('/api/ai/mcp-servers/{server_id}/tools/{tool_id}/block', {
              params: { path },
              body,
            }),
      )
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: mcpKeys.tools(serverId) })
      refresh()
    },
  })
}
