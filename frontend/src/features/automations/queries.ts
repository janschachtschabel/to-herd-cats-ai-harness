import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { pagedQuery, usePaged } from '@/lib/paging'

export type Automation = Schemas['AutomationOut']
export type Firing = Schemas['FiringOut']
export type ScheduleIn = Schemas['AutomationCreate']['schedule']

/** The query keys of automations: lists under `['automations', 'list']`, so one
 *  `automation.changed` refreshes every list shown. */
export const automationKeys = {
  all: ['automations'] as const,
  lists: ['automations', 'list'] as const,
  mine: ['automations', 'list', 'mine'] as const,
  agent: (agentId: string) => ['automations', 'list', 'agent', agentId] as const,
  space: (spaceId: string) => ['automations', 'list', 'space', spaceId] as const,
  details: ['automations', 'detail'] as const,
  detail: (id: string) => ['automations', 'detail', id] as const,
  allFirings: ['automations', 'firings'] as const,
  firings: (id: string) => ['automations', 'firings', id] as const,
  preview: (schedule: ScheduleIn | null) => ['automations', 'preview', schedule] as const,
}

const LIMIT = 50

export const myAutomationsQuery = pagedQuery(automationKeys.mine, async (cursor) =>
  unwrap(await api.GET('/api/automations', { params: { query: { cursor, limit: LIMIT } } })),
)

/** My automations, newest first (`ai.use`). */
export function useMyAutomations() {
  return usePaged(myAutomationsQuery)
}

/** An agent's automations (`agent.manage`). */
export function useAgentAutomations(agentId: string) {
  return usePaged(
    pagedQuery(automationKeys.agent(agentId), async (cursor) =>
      unwrap(
        await api.GET('/api/agents/{agent_id}/automations', {
          params: { path: { agent_id: agentId }, query: { cursor, limit: LIMIT } },
        }),
      ),
    ),
  )
}

/** The automations at places of a space that I see. */
export function useSpaceAutomations(spaceId: string) {
  return usePaged(
    pagedQuery(automationKeys.space(spaceId), async (cursor) =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/automations', {
          params: { path: { space_id: spaceId }, query: { cursor, limit: LIMIT } },
        }),
      ),
    ),
  )
}

export const automationQuery = (id: string) =>
  queryOptions({
    queryKey: automationKeys.detail(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/automations/{automation_id}', {
          params: { path: { automation_id: id } },
        }),
      ),
  })

export function useAutomation(id: string) {
  return useQuery(automationQuery(id))
}

/** The log of its terms, newest first. */
export function useFirings(id: string) {
  return usePaged(
    pagedQuery(automationKeys.firings(id), async (cursor) =>
      unwrap(
        await api.GET('/api/automations/{automation_id}/firings', {
          params: { path: { automation_id: id }, query: { cursor, limit: LIMIT } },
        }),
      ),
    ),
  )
}

/** The next terms of a schedule as typed (asked once typing settles; none for event
 *  rules or an unfinished schedule). */
export function useTermPreview(schedule: ScheduleIn | null) {
  const settled = useDebouncedValue(schedule, 400)
  return useQuery({
    queryKey: automationKeys.preview(settled),
    enabled: settled !== null && settled.kind !== 'event',
    retry: false,
    staleTime: 30_000,
    queryFn: async () =>
      unwrap(await api.POST('/api/automations/preview', { body: { schedule: settled! } })).terms,
  })
}

/** What `automation.changed` makes stale: every list (it may have appeared in or left
 *  one), the automation and its log; never a preview. */
export function automationEventKeys(id: string | null): (readonly unknown[])[] {
  const keys: (readonly unknown[])[] = [automationKeys.lists]
  if (id) keys.push(automationKeys.detail(id), automationKeys.firings(id))
  return keys
}

/** Everything shown of automations is stale (one changed). */
export function refreshAutomations(queryClient: QueryClient, id?: string) {
  void queryClient.invalidateQueries({ queryKey: automationKeys.lists })
  if (id) {
    void queryClient.invalidateQueries({ queryKey: automationKeys.detail(id) })
    void queryClient.invalidateQueries({ queryKey: automationKeys.firings(id) })
  }
}

function useChange<A>(run: (args: A) => Promise<Automation | undefined>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSuccess: (saved) => {
      if (saved) queryClient.setQueryData(automationKeys.detail(saved.id), saved)
    },
    onSettled: (saved) => refreshAutomations(queryClient, saved?.id),
  })
}

export function useCreateAutomation() {
  return useChange(async (body: Schemas['AutomationCreate']) =>
    unwrap(await api.POST('/api/automations', { body })),
  )
}

export function useUpdateAutomation(id: string) {
  return useChange(async (body: Schemas['AutomationUpdate']) =>
    unwrap(
      await api.PATCH('/api/automations/{automation_id}', {
        params: { path: { automation_id: id } },
        body,
      }),
    ),
  )
}

export type ControlAction = 'pause' | 'resume' | 'take-over'

/** Pause, resume or take over, against the version read (409 when stale). */
export function useControlAutomation(id: string) {
  return useChange(async ({ action, version }: { action: ControlAction; version: number }) => {
    const params = { path: { automation_id: id } }
    const body = { version }
    if (action === 'pause') {
      return unwrap(await api.POST('/api/automations/{automation_id}/pause', { params, body }))
    }
    if (action === 'resume') {
      return unwrap(await api.POST('/api/automations/{automation_id}/resume', { params, body }))
    }
    return unwrap(await api.POST('/api/automations/{automation_id}/take-over', { params, body }))
  })
}

/** One term out of turn (its owner); the answer's `last_run` tells how it went. */
export function useRunAutomation(id: string) {
  return useChange(async () =>
    unwrap(
      await api.POST('/api/automations/{automation_id}/run', {
        params: { path: { automation_id: id } },
      }),
    ),
  )
}

export function useDeleteAutomation(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (version: number) =>
      unwrap(
        await api.DELETE('/api/automations/{automation_id}', {
          params: { path: { automation_id: id }, query: { version } },
        }),
      ),
    onSuccess: () => queryClient.removeQueries({ queryKey: automationKeys.detail(id) }),
    onSettled: () => refreshAutomations(queryClient),
  })
}

/** Loads the automation again (after a stale version): it as the server has it now. */
export function useReloadAutomation(id: string) {
  const queryClient = useQueryClient()
  return () => queryClient.fetchQuery({ ...automationQuery(id), staleTime: 0 })
}
