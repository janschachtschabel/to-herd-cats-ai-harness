import type { QueryClient } from '@tanstack/react-query'
import { ticketKeys } from './keys'

type Key = readonly unknown[]

/** The cached lists that show `spaceId` (`all`: also those spanning every space). */
function spaceLists(queryClient: QueryClient, spaceId: string, all: boolean): Key[] {
  const keys: Key[] = []
  for (const query of queryClient.getQueryCache().findAll({ queryKey: ticketKeys.lists })) {
    const filters = query.queryKey[2] as { space?: string } | undefined
    if (filters?.space ? filters.space === spaceId : all) keys.push(query.queryKey)
  }
  return keys
}

/** The ticket queries a `ticket.created` / `ticket.updated` can change (review M4 P4):
 *  the ticket itself (found by its id in the cached tickets) with its page links, the
 *  lists that span every space or show its space, its space's board, columns, epics
 *  and parent picks, the counter, my board (it spans every space), and the children
 *  and page-ticket lists (keyed by ids the event does not name; only the ones on
 *  screen refetch). Without the space (an older server), every ticket query. */
export function ticketEventKeys(
  queryClient: QueryClient,
  ticketId: string | null,
  spaceId: string | null,
): Key[] {
  if (!spaceId) return [ticketKeys.all]
  const keys: Key[] = [
    ticketKeys.counts,
    ['tickets', 'board', spaceId],
    ['tickets', 'column', spaceId],
    ticketKeys.epics(spaceId),
    ['tickets', 'parents', spaceId],
    ['tickets', 'children'],
    ['tickets', 'page'],
    ticketKeys.myBoard,
    ...spaceLists(queryClient, spaceId, true),
  ]
  if (ticketId) {
    for (const query of queryClient.getQueryCache().findAll({ queryKey: ['tickets', 'detail'] })) {
      const data = query.state.data as { id?: string; number?: number } | undefined
      if (data?.id === ticketId && data.number !== undefined)
        keys.push(query.queryKey, ticketKeys.pages(data.number))
    }
  }
  return keys
}

/** What a `sprint.changed` can change (plan M4b): the space's sprints, its boards (a
 *  sprint filter, the daily view's preset) and the lists of that space (backlog, a
 *  sprint's tickets). Moved tickets come as `ticket.updated` of their own. */
export function sprintEventKeys(queryClient: QueryClient, spaceId: string | null): Key[] {
  if (!spaceId) return [ticketKeys.all]
  return [
    ['tickets', 'board', spaceId],
    ['tickets', 'column', spaceId],
    ticketKeys.sprints(spaceId),
    ...spaceLists(queryClient, spaceId, false),
  ]
}
