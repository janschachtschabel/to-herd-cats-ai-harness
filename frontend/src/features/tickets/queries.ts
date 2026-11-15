import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { api, ApiError, unwrap, type Schemas, type Ticket, type TicketSummary } from '@/lib/api'
import type { TicketKind } from './display'
import { pagedQuery, usePaged } from '@/lib/paging'
import { listQuery, type TicketSearch } from './filters'
import { ticketKeys } from './keys'

const PAGE_SIZE = 50

/** Gone is gone (404 for a ticket one may not see, the same as a free number). */
const noRetryOn404 = (failures: number, error: unknown) =>
  !(error instanceof ApiError && error.status === 404) && failures < 1

export const ticketListQuery = (search: TicketSearch) =>
  pagedQuery(ticketKeys.list(search), async (cursor) =>
    unwrap(
      await api.GET('/api/tickets', {
        params: { query: { ...listQuery(search), cursor, limit: PAGE_SIZE } },
      }),
    ),
  )

export const ticketQuery = (number: number) =>
  queryOptions({
    queryKey: ticketKeys.detail(number),
    queryFn: async () =>
      unwrap(await api.GET('/api/tickets/{number}', { params: { path: { number } } })),
    retry: noRetryOn404,
  })

export const ticketCountsQuery = queryOptions({
  queryKey: ticketKeys.counts,
  queryFn: async () => unwrap(await api.GET('/api/tickets/counts')),
})

/** A space's statuses in their order (at most 20 per space: one request). */
export const statusesQuery = (spaceId: string) =>
  queryOptions({
    queryKey: ticketKeys.statuses(spaceId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/spaces/{space_id}/ticket-statuses', {
          params: { path: { space_id: spaceId }, query: { limit: 100 } },
        }),
      ).items,
  })

export function useTickets(search: TicketSearch) {
  return usePaged(ticketListQuery(search))
}

export function useTicket(number: number) {
  return useQuery(ticketQuery(number))
}

/** My unfinished tickets (the sidebar's counter). */
export function useTicketCount(): number {
  return useQuery(ticketCountsQuery).data?.assigned_open ?? 0
}

export function useStatuses(spaceId: string | undefined) {
  return useQuery({ ...statusesQuery(spaceId ?? ''), enabled: spaceId !== undefined })
}

/** A ticket's children (one page of up to 100, by number). */
export function useChildren(parentId: string, enabled = true) {
  return useQuery({
    queryKey: ticketKeys.children(parentId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/tickets', {
          params: { query: { parent: parentId, limit: 100, sort: 'number' } },
        }),
      ),
    enabled,
  })
}

/** Every ticket view after a change: the ticket as returned, the rest refetched. */
export function storeTicket(queryClient: QueryClient, ticket: Ticket): void {
  queryClient.setQueryData(ticketKeys.detail(ticket.number), ticket)
  void queryClient.invalidateQueries({
    queryKey: ticketKeys.all,
    predicate: (query) => query.queryKey[1] !== 'detail' || query.queryKey[2] !== ticket.number,
  })
}

export function useCreateTicket(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['TicketCreate']) =>
      unwrap(
        await api.POST('/api/spaces/{space_id}/tickets', {
          params: { path: { space_id: spaceId } },
          body,
        }),
      ),
    onSuccess: (ticket) => storeTicket(queryClient, ticket),
  })
}

export type TicketChange = Omit<Schemas['TicketUpdate'], 'version'>

/** Changes fields of the ticket as last read (its `version`); a stale one is 409
 *  `ticket.version_conflict`, which the view offers to reload. */
export function useUpdateTicket(ticket: Pick<Ticket, 'number' | 'version'>) {
  const queryClient = useQueryClient()
  return useMutation({
    // `base`: the version a draft was opened at (a text edit); otherwise the one shown.
    mutationFn: async ({ base, ...change }: TicketChange & { base?: number }) =>
      unwrap(
        await api.PATCH('/api/tickets/{number}', {
          params: { path: { number: ticket.number } },
          body: { ...change, version: base ?? ticket.version },
        }),
      ),
    onSuccess: (updated) => storeTicket(queryClient, updated),
  })
}

export function useSetTicketTags(ticket: Ticket) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ tagIds, base }: { tagIds: string[]; base: number }) =>
      unwrap(
        await api.PUT('/api/tickets/{number}/tags', {
          params: { path: { number: ticket.number } },
          body: { tag_ids: tagIds, version: base },
        }),
      ),
    onSuccess: (updated) => storeTicket(queryClient, updated),
  })
}

/** The ticket as the server has it now (after "changed in the meantime"). */
export function useReloadTicket(number: number) {
  const queryClient = useQueryClient()
  return () => queryClient.fetchQuery({ ...ticketQuery(number), staleTime: 0 })
}

export function useTicketThread(number: number) {
  return useQuery({
    queryKey: ticketKeys.thread(number),
    queryFn: async () =>
      unwrap(await api.GET('/api/tickets/{number}/thread', { params: { path: { number } } })),
    staleTime: 5 * 60_000,
  })
}

/** The tickets of a space that can be the parent of a ticket of some kind: up to 100
 *  of each of `kinds` (epics, stories), newest number first. Asked while `enabled`. */
export function useParentCandidates(spaceId: string, kinds: TicketKind[], enabled: boolean) {
  return useQuery({
    queryKey: ticketKeys.parents(spaceId, kinds.join(',')),
    queryFn: async () => {
      const found: TicketSummary[] = []
      for (const kind of kinds) {
        const page = unwrap(
          await api.GET('/api/tickets', {
            params: { query: { space_id: spaceId, kind, limit: 100, sort: 'number' } },
          }),
        )
        found.push(...page.items)
      }
      return found
    },
    enabled: enabled && kinds.length > 0,
  })
}
