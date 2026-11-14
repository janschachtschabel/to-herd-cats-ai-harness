import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, unwrap, type Schemas, type Sprint, type TicketSummary } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { ticketKeys } from '../keys'
import { UNFINISHED } from '../display'

/** A space's sprints in the server's order: the active one, the planned ones (earliest
 *  start first), then the closed ones (latest end first). */
export const sprintsQuery = (spaceId: string) =>
  pagedQuery([...ticketKeys.sprints(spaceId), 'all'], async (cursor) =>
    unwrap(
      await api.GET('/api/spaces/{space_id}/sprints', {
        params: { path: { space_id: spaceId }, query: { cursor, limit: 50 } },
      }),
    ),
  )

export function useSprints(spaceId: string) {
  return usePaged(sprintsQuery(spaceId))
}

/** The sprints a ticket can go into (active and planned, listed first) and the closed
 *  ones of the first page: one request of at most 100. A ticket names its own sprint
 *  (`Ticket.sprint`). */
export const sprintChoicesQuery = (spaceId: string) =>
  queryOptions({
    queryKey: [...ticketKeys.sprints(spaceId), 'choices'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/sprints', {
          params: { path: { space_id: spaceId }, query: { limit: 100 } },
        }),
      ).items,
  })

export function useSprintChoices(spaceId: string | undefined, enabled = true) {
  return useQuery({
    ...sprintChoicesQuery(spaceId ?? ''),
    enabled: enabled && spaceId !== undefined,
  })
}

/** What to offer as a target: the active sprint first, then the planned ones. */
export function openSprints(sprints: Sprint[] | undefined): Sprint[] {
  return (sprints ?? []).filter((s) => s.state !== 'closed')
}

/** The tickets of a space in `sprint` (an id, or `none`: the backlog), by priority;
 *  `unfinished` leaves out what is done or cancelled. */
export const sprintTicketsQuery = (spaceId: string, sprint: string, unfinished: boolean) =>
  pagedQuery(ticketKeys.list({ space: spaceId, sprint, unfinished }), async (cursor) =>
    unwrap(
      await api.GET('/api/tickets', {
        params: {
          query: {
            space_id: spaceId,
            sprint,
            sort: 'priority',
            status_category: unfinished ? [...UNFINISHED] : undefined,
            cursor,
            limit: 50,
          },
        },
      }),
    ),
  )

export function useSprintTickets(spaceId: string, sprint: string, unfinished = false) {
  return usePaged(sprintTicketsQuery(spaceId, sprint, unfinished))
}

/** After a sprint changed (or a change was refused): every ticket view, since closing
 *  moves tickets and a refusal means the sprint list is stale. */
function useRefreshTickets() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
}

export function useCreateSprint(spaceId: string) {
  const refresh = useRefreshTickets()
  return useMutation({
    mutationFn: async (body: Schemas['SprintCreate']) =>
      unwrap(
        await api.POST('/api/spaces/{space_id}/sprints', {
          params: { path: { space_id: spaceId } },
          body,
        }),
      ),
    onSuccess: refresh,
  })
}

/** Starts a planned sprint, with the version read (409 `sprint.active_exists` while
 *  another runs). */
export function useStartSprint(sprint: Sprint) {
  const refresh = useRefreshTickets()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/sprints/{sprint_id}/start', {
          params: { path: { sprint_id: sprint.id } },
          body: { version: sprint.version },
        }),
      ),
    onSettled: refresh,
  })
}

/** Closes the active sprint; its unfinished tickets go to the next planned sprint or
 *  back into the backlog. */
export function useCloseSprint(sprint: Sprint) {
  const refresh = useRefreshTickets()
  return useMutation({
    mutationFn: async (moveOpenTo: Schemas['MoveOpenTo']) =>
      unwrap(
        await api.POST('/api/sprints/{sprint_id}/close', {
          params: { path: { sprint_id: sprint.id } },
          body: { version: sprint.version, move_open_to: moveOpenTo },
        }),
      ),
    onSettled: refresh,
  })
}

/** How a batch of moves went: those moved, those changed in the meantime (409), and
 *  the first other refusal. */
export interface BatchResult {
  moved: number
  stale: number
  failed: number
  error: unknown
}

/** Puts tickets into a sprint (or the backlog: null), one request each with the version
 *  the list showed; a ticket changed in the meantime stays where it is. */
export function usePutIntoSprint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      tickets,
      sprintId,
    }: {
      tickets: TicketSummary[]
      sprintId: string | null
    }): Promise<BatchResult> => {
      const result: BatchResult = { moved: 0, stale: 0, failed: 0, error: null }
      for (const ticket of tickets) {
        try {
          const updated = unwrap(
            await api.PATCH('/api/tickets/{number}', {
              params: { path: { number: ticket.number } },
              body: { sprint_id: sprintId, version: ticket.version },
            }),
          )
          queryClient.setQueryData(ticketKeys.detail(updated.number), updated)
          result.moved += 1
        } catch (error) {
          if (error instanceof ApiError && error.isVersionConflict) result.stale += 1
          else {
            result.failed += 1
            result.error ??= error
          }
        }
      }
      return result
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ticketKeys.all }),
  })
}
