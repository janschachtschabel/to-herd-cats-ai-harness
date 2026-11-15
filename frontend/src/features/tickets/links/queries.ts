import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { ticketKeys } from '../keys'

/** The pages a ticket links that the caller sees, last linked first. */
export function useTicketPages(number: number) {
  return usePaged(
    pagedQuery(ticketKeys.pages(number), async (cursor) =>
      unwrap(
        await api.GET('/api/tickets/{number}/pages', {
          params: { path: { number }, query: { cursor, limit: 50 } },
        }),
      ),
    ),
  )
}

/** The tickets linked to a page that the caller sees, newest number first. */
export function usePageTickets(pageId: string) {
  return usePaged(
    pagedQuery(ticketKeys.pageTickets(pageId), async (cursor) =>
      unwrap(
        await api.GET('/api/pages/{page_id}/tickets', {
          params: { path: { page_id: pageId }, query: { cursor, limit: 50 } },
        }),
      ),
    ),
  )
}

/** Links or unlinks a page (both idempotent; no version: a set membership). Both
 *  sides refresh: the ticket's pages and the page's tickets live under `tickets`. */
export function useLinkPage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      number,
      pageId,
      link,
    }: {
      number: number
      pageId: string
      link: boolean
    }) => {
      const params = { params: { path: { number, page_id: pageId } } }
      return unwrap(
        link
          ? await api.PUT('/api/tickets/{number}/pages/{page_id}', params)
          : await api.DELETE('/api/tickets/{number}/pages/{page_id}', params),
      )
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ticketKeys.all }),
  })
}

/** What a search finds of one type (pages to link, tickets to link), for the
 *  pickers; nothing is asked while `q` is blank. */
export function useFind(type: 'page' | 'ticket', q: string) {
  return useQuery({
    queryKey: ['search', 'pick', type, q],
    queryFn: async () =>
      unwrap(await api.GET('/api/search', { params: { query: { q, types: type, limit: 10 } } }))
        .items,
    enabled: q.trim() !== '',
  })
}
