import type { QueryClient } from '@tanstack/react-query'
import { ticketKeys } from './keys'

type Key = readonly unknown[]

/** The ticket queries a `ticket.created` / `ticket.updated` can change (review M4 P4):
 *  the ticket itself (found by its id in the cached tickets) with its page links, the
 *  lists that span every space or show its space, its space's board, columns, epics
 *  and parent picks, the counter, and the children and page-ticket lists (keyed by
 *  ids the event does not name; only the ones on screen refetch). Without the space
 *  (an older server), every ticket query. */
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
  ]
  const cache = queryClient.getQueryCache()
  for (const query of cache.findAll({ queryKey: ticketKeys.lists })) {
    const filters = query.queryKey[2] as { space?: string } | undefined
    if (!filters?.space || filters.space === spaceId) keys.push(query.queryKey)
  }
  if (ticketId) {
    for (const query of cache.findAll({ queryKey: ['tickets', 'detail'] })) {
      const data = query.state.data as { id?: string; number?: number } | undefined
      if (data?.id === ticketId && data.number !== undefined)
        keys.push(query.queryKey, ticketKeys.pages(data.number))
    }
  }
  return keys
}
