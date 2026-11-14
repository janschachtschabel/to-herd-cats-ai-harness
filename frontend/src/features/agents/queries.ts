import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { messagingKeys } from '@/features/messaging/keys'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { agentKeys, type ActiveRun } from './keys'

export type Agent = Schemas['AgentOut']
export type Run = Schemas['RunOut']
export type RunEvent = Schemas['RunEventOut']

export const agentsQuery = pagedQuery(agentKeys.list, async (cursor) =>
  unwrap(await api.GET('/api/agents', { params: { query: { cursor } } })),
)

export const agentQuery = (agentId: string) =>
  queryOptions({
    queryKey: agentKeys.detail(agentId),
    queryFn: async () =>
      unwrap(await api.GET('/api/agents/{agent_id}', { params: { path: { agent_id: agentId } } })),
  })

/** The agents (`agent.manage`; everyone else gets 404 and never asks). */
export function useAgents() {
  return usePaged(agentsQuery)
}

export function useCreateAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['AgentCreate']) =>
      unwrap(await api.POST('/api/agents', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: agentKeys.all }),
  })
}

export function useUpdateAgent(agentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['AgentUpdate']) =>
      unwrap(
        await api.PATCH('/api/agents/{agent_id}', {
          params: { path: { agent_id: agentId } },
          body,
        }),
      ),
    onSuccess: (agent) => {
      queryClient.setQueryData(agentQuery(agentId).queryKey, agent)
      void queryClient.invalidateQueries({ queryKey: agentKeys.list })
      void queryClient.invalidateQueries({ queryKey: agentKeys.profile(agentId) })
    },
  })
}

export function useDeleteAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.DELETE('/api/agents/{agent_id}', {
          params: { path: { agent_id: id }, query: { version } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: agentKeys.list }),
  })
}

/** What everyone with `ai.use` may know of an agent: name, introduction, status. */
export function useAgentProfile(agentId: string | null) {
  return useQuery({
    queryKey: agentKeys.profile(agentId ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/agents/{agent_id}/profile', {
          params: { path: { agent_id: agentId ?? '' } },
        }),
      ),
    enabled: agentId !== null,
  })
}

/** Opens (or finds again) my direct message with an agent. */
export function useOpenAgentDm() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (agentId: string) =>
      unwrap(await api.POST('/api/dms', { body: { agent_id: agentId } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: messagingKeys.dms }),
  })
}

/** A run, for whom it concerns (the person who asked, the responsible person, agent
 *  admins); refreshed by `run.progress` and new messages, never polled. */
export function useRun(runId: string | null) {
  return useQuery({
    queryKey: agentKeys.run(runId ?? ''),
    queryFn: async () =>
      unwrap(await api.GET('/api/runs/{run_id}', { params: { path: { run_id: runId ?? '' } } })),
    enabled: runId !== null,
  })
}

/** A run's steps (first page: a level-1 run has at most 25). Asked only while `enabled`. */
export function useRunEvents(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: agentKeys.runEvents(runId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/runs/{run_id}/events', {
          params: { path: { run_id: runId }, query: { limit: 100 } },
        }),
      ),
    enabled,
  })
}

export function setActiveRun(queryClient: QueryClient, conversationId: string, run: ActiveRun) {
  queryClient.setQueryData(agentKeys.activeRun(conversationId), run)
}

/** The run this page last heard of in a direct message, if any. */
export function useActiveRun(conversationId: string): ActiveRun | null {
  return (
    useQuery<ActiveRun | null>({
      queryKey: agentKeys.activeRun(conversationId),
      queryFn: () => null,
      enabled: false,
      staleTime: Infinity,
    }).data ?? null
  )
}

/** After sending (to an agent in a direct message, or mentioning one elsewhere):
 *  follows the run it started, or returns why none started (`agent_run.reason`, to be
 *  put in words). Outside a direct message the run answers in the message's thread. */
export function useNoteAgentRun(conversationId: string, inThreads: boolean) {
  const queryClient = useQueryClient()
  return (written: Schemas['MessageWriteOut'] | null): string | null => {
    const run = written?.agent_run
    if (!written || !run) return null
    if (run.id) {
      const threadId = inThreads ? (written.parent_id ?? written.id) : null
      setActiveRun(queryClient, conversationId, { runId: run.id, step: null, threadId })
      return null
    }
    return run.reason
  }
}
