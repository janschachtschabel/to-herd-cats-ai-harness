import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { meQuery } from '@/features/auth/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type Token = Schemas['TokenOut']
export type AdminToken = Schemas['AdminTokenOut']
export type CreatedToken = Schemas['TokenCreatedOut']
export type TokenCall = Schemas['McpCallOut']
export type McpSettings = Schemas['McpSettingsOut']

/** The query keys of access tokens (plan M8): mine, the organisation's (admins), an
 *  external agent's, the calls of one, and the MCP settings. */
export const tokenKeys = {
  all: ['tokens'] as const,
  mine: ['tokens', 'mine'] as const,
  org: ['tokens', 'org'] as const,
  agent: (agentId: string) => ['tokens', 'agent', agentId] as const,
  calls: (owner: string, tokenId: string) => ['tokens', 'calls', owner, tokenId] as const,
  settings: ['tokens', 'mcp-settings'] as const,
}

/** Where a token's calls are read: my own, any of the organisation's, an agent's. */
export type CallsOwner = { kind: 'mine' } | { kind: 'org' } | { kind: 'agent'; agentId: string }

function ownerKey(owner: CallsOwner): string {
  return owner.kind === 'agent' ? `agent:${owner.agentId}` : owner.kind
}

/** My personal tokens (`mcp.use`; anyone else gets 404 and never asks). */
export function useMyTokens() {
  return usePaged(
    pagedQuery(tokenKeys.mine, async (cursor) =>
      unwrap(await api.GET('/api/tokens', { params: { query: { cursor } } })),
    ),
  )
}

/** Every token of the organisation, metadata only (`ai.manage`). */
export function useOrgTokens() {
  return usePaged(
    pagedQuery(tokenKeys.org, async (cursor) =>
      unwrap(await api.GET('/api/ai/mcp/tokens', { params: { query: { cursor } } })),
    ),
  )
}

/** An external agent's tokens (`agent.manage`). */
export function useAgentTokens(agentId: string) {
  return usePaged(
    pagedQuery(tokenKeys.agent(agentId), async (cursor) =>
      unwrap(
        await api.GET('/api/agents/{agent_id}/tokens', {
          params: { path: { agent_id: agentId }, query: { cursor } },
        }),
      ),
    ),
  )
}

async function fetchCalls(owner: CallsOwner, tokenId: string, cursor: string | undefined) {
  const query = { cursor }
  if (owner.kind === 'mine') {
    return unwrap(
      await api.GET('/api/tokens/{token_id}/calls', {
        params: { path: { token_id: tokenId }, query },
      }),
    )
  }
  if (owner.kind === 'org') {
    return unwrap(
      await api.GET('/api/ai/mcp/tokens/{token_id}/calls', {
        params: { path: { token_id: tokenId }, query },
      }),
    )
  }
  return unwrap(
    await api.GET('/api/agents/{agent_id}/tokens/{token_id}/calls', {
      params: { path: { agent_id: owner.agentId, token_id: tokenId }, query },
    }),
  )
}

/** A token's recent calls through `/mcp`, newest first (ids, tool, outcome only). */
export function useTokenCalls(owner: CallsOwner, tokenId: string) {
  return usePaged(
    pagedQuery(tokenKeys.calls(ownerKey(owner), tokenId), (cursor) =>
      fetchCalls(owner, tokenId, cursor),
    ),
  )
}

/** Creates a token: mine, or an external agent's. The answer carries the clear text
 *  once (`secret`); it is handed on and kept nowhere in the cache: the finished
 *  mutation is forgotten as soon as its form is gone (`gcTime: 0`, module review M8 2,
 *  finding G3), and the form resets it once it has handed the token on. */
export function useCreateToken(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    gcTime: 0,
    mutationFn: async (body: Schemas['TokenIn']) =>
      agentId
        ? unwrap(
            await api.POST('/api/agents/{agent_id}/tokens', {
              params: { path: { agent_id: agentId } },
              body,
            }),
          )
        : unwrap(await api.POST('/api/tokens', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: tokenKeys.all }),
  })
}

/** Revokes a token where it is listed (idempotent: 204 also for one already revoked). */
export function useRevokeToken(owner: CallsOwner) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (tokenId: string) => {
      if (owner.kind === 'mine') {
        return unwrap(
          await api.DELETE('/api/tokens/{token_id}', { params: { path: { token_id: tokenId } } }),
        )
      }
      if (owner.kind === 'org') {
        return unwrap(
          await api.DELETE('/api/ai/mcp/tokens/{token_id}', {
            params: { path: { token_id: tokenId } },
          }),
        )
      }
      return unwrap(
        await api.DELETE('/api/agents/{agent_id}/tokens/{token_id}', {
          params: { path: { agent_id: owner.agentId, token_id: tokenId } },
        }),
      )
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: tokenKeys.all }),
  })
}

export const mcpSettingsQuery = queryOptions({
  queryKey: tokenKeys.settings,
  queryFn: async () => unwrap(await api.GET('/api/ai/mcp')),
})

/** The organisation's MCP switch and data location (`ai.manage`). */
export function useMcpSettings() {
  return useQuery(mcpSettingsQuery)
}

/** Saves switch and data location at the read version (409: stale, reload). Turning
 *  the switch changes who holds `mcp.use`, so `/auth/me` is read again. */
export function useSaveMcpSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['McpSettingsIn']) =>
      unwrap(await api.PUT('/api/ai/mcp', { body })),
    onSuccess: (saved) => {
      queryClient.setQueryData(tokenKeys.settings, saved)
      void queryClient.invalidateQueries({ queryKey: meQuery.queryKey })
    },
  })
}
