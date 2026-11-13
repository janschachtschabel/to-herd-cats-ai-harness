import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import type { Ticket } from '@/lib/api'
import { ticketQuery, useUpdateTicket } from './queries'

/** A change to the ticket as last read; after "changed in the meantime" (409),
 *  `reload` fetches the current ticket and clears the error, and whatever the person
 *  typed stays where it is, to be saved again. */
export function useTicketSave(ticket: Ticket) {
  const queryClient = useQueryClient()
  const update = useUpdateTicket(ticket)
  const { reset } = update
  const reload = useCallback(async () => {
    await queryClient.fetchQuery({ ...ticketQuery(ticket.number), staleTime: 0 })
    reset()
  }, [queryClient, ticket.number, reset])
  return { ...update, reload }
}
