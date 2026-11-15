import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { agentKeys } from './keys'
import { agentQuery } from './queries'

/** What an agent's managers set besides its fields: level, tool grants, skills (all
 *  versioned with the agent), and the spaces it is a member of. Every write changes
 *  the agent's version, so each refreshes all of them. */
export const agentAdminKeys = {
  tools: (id: string) => ['agents', 'detail', id, 'tools'] as const,
  spaces: (id: string) => ['agents', 'detail', id, 'spaces'] as const,
  skills: (id: string) => ['agents', 'detail', id, 'skills'] as const,
}

export const agentToolsQuery = (agentId: string) =>
  queryOptions({
    queryKey: agentAdminKeys.tools(agentId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/agents/{agent_id}/tools', { params: { path: { agent_id: agentId } } }),
      ),
  })

export const agentSkillsQuery = (agentId: string) =>
  queryOptions({
    queryKey: agentAdminKeys.skills(agentId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/agents/{agent_id}/skills', { params: { path: { agent_id: agentId } } }),
      ),
  })

export function useAgent(agentId: string) {
  return useQuery(agentQuery(agentId))
}

export function useAgentTools(agentId: string) {
  return useQuery(agentToolsQuery(agentId))
}

export function useAgentSkills(agentId: string) {
  return useQuery(agentSkillsQuery(agentId))
}

export function useAgentSpaces(agentId: string) {
  return usePaged(
    pagedQuery(agentAdminKeys.spaces(agentId), async (cursor) =>
      unwrap(
        await api.GET('/api/agents/{agent_id}/spaces', {
          params: { path: { agent_id: agentId }, query: { cursor } },
        }),
      ),
    ),
  )
}

function useRefreshAgent(agentId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: agentKeys.detail(agentId) })
    void queryClient.invalidateQueries({ queryKey: agentKeys.list })
  }
}

export function useSetAgentLevel(agentId: string) {
  const refresh = useRefreshAgent(agentId)
  return useMutation({
    mutationFn: async (body: { level: number; version: number }) =>
      unwrap(
        await api.PATCH('/api/agents/{agent_id}', {
          params: { path: { agent_id: agentId } },
          body,
        }),
      ),
    onSettled: refresh,
  })
}

export function useSetAgentTools(agentId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshAgent(agentId)
  return useMutation({
    mutationFn: async (body: Schemas['AgentToolsPut']) =>
      unwrap(
        await api.PUT('/api/agents/{agent_id}/tools', {
          params: { path: { agent_id: agentId } },
          body,
        }),
      ),
    onSuccess: (shown) => queryClient.setQueryData(agentToolsQuery(agentId).queryKey, shown),
    onSettled: refresh,
  })
}

export function useSetAgentSkills(agentId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshAgent(agentId)
  return useMutation({
    mutationFn: async (body: Schemas['AgentSkillsPut']) =>
      unwrap(
        await api.PUT('/api/agents/{agent_id}/skills', {
          params: { path: { agent_id: agentId } },
          body,
        }),
      ),
    onSuccess: (shown) => queryClient.setQueryData(agentSkillsQuery(agentId).queryKey, shown),
    onSettled: refresh,
  })
}
