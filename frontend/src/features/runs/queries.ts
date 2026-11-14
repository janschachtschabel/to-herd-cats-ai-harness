import { useMutation, useQueryClient } from '@tanstack/react-query'
import { agentKeys } from '@/features/agents/keys'
import type { Run } from '@/features/agents/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type RunState = Schemas['RunState']
export type StopReason = Schemas['StopReason']

/** The filters of a run list (they stand in the address). */
export interface RunFilters {
  state?: RunState
  stop_reason?: StopReason
}

/** Run lists share the runs' prefix, so whatever refreshes runs refreshes them too. */
export const runKeys = {
  list: (scope: string, filters: RunFilters) =>
    [...agentKeys.runs, 'list', scope, filters] as const,
  timeline: (runId: string) => [...agentKeys.runEvents(runId), 'all'] as const,
}

const PAGE = 50

/** "My runs": the runs I asked for, newest first (`ai.use` or `agent.manage`). */
export const myRunsQuery = (filters: RunFilters) =>
  pagedQuery(runKeys.list('mine', filters), async (cursor) =>
    unwrap(await api.GET('/api/runs', { params: { query: { cursor, limit: PAGE, ...filters } } })),
  )

export function useMyRuns(filters: RunFilters) {
  return usePaged(myRunsQuery(filters))
}

/** Every run of an agent, for its responsible person, its owner and agent admins
 *  (everyone else gets 404 `agent.not_found`). */
export const agentRunsQuery = (agentId: string, filters: RunFilters) =>
  pagedQuery(runKeys.list(`agent:${agentId}`, filters), async (cursor) =>
    unwrap(
      await api.GET('/api/agents/{agent_id}/runs', {
        params: { path: { agent_id: agentId }, query: { cursor, limit: PAGE, ...filters } },
      }),
    ),
  )

export function useAgentRuns(agentId: string, filters: RunFilters) {
  return usePaged(agentRunsQuery(agentId, filters))
}

/** A run's steps in the order they happened (redacted where the reader may not read). */
export const runTimelineQuery = (runId: string) =>
  pagedQuery(runKeys.timeline(runId), async (cursor) =>
    unwrap(
      await api.GET('/api/runs/{run_id}/events', {
        params: { path: { run_id: runId }, query: { cursor, limit: 100 } },
      }),
    ),
  )

export function useRunTimeline(runId: string) {
  return usePaged(runTimelineQuery(runId))
}

/** Asks the run to stop (once; again answers the same; 409 `run.finished`). */
export function useCancelRun(runId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/runs/{run_id}/cancel', { params: { path: { run_id: runId } } })),
    onSuccess: (run: Run) => {
      queryClient.setQueryData(agentKeys.run(runId), run)
      void queryClient.invalidateQueries({ queryKey: agentKeys.runs })
      void queryClient.invalidateQueries({ queryKey: agentKeys.runEvents(runId) })
    },
    onError: () => void queryClient.invalidateQueries({ queryKey: agentKeys.run(runId) }),
  })
}
