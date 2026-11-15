import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas, type TicketStatus } from '@/lib/api'
import { ticketKeys } from '../keys'

/** After any change to a workflow every ticket view may read differently (column
 *  names, order, moved tickets): all of them refresh. */
function useStatusMutation<T>(run: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ticketKeys.all }),
  })
}

export function useCreateStatus(spaceId: string) {
  return useStatusMutation(async (body: Schemas['StatusCreate']) =>
    unwrap(
      await api.POST('/api/spaces/{space_id}/ticket-statuses', {
        params: { path: { space_id: spaceId } },
        body,
      }),
    ),
  )
}

export function useUpdateStatus(status: TicketStatus) {
  return useStatusMutation(async (change: Omit<Schemas['StatusUpdate'], 'version'>) =>
    unwrap(
      await api.PATCH('/api/ticket-statuses/{status_id}', {
        params: { path: { status_id: status.id } },
        body: { ...change, version: status.version },
      }),
    ),
  )
}

/** Deletes the status; its tickets (if any) go to `replaceWith`. */
export function useDeleteStatus(status: TicketStatus) {
  return useStatusMutation(async (replaceWith: string) =>
    unwrap(
      await api.DELETE('/api/ticket-statuses/{status_id}', {
        params: {
          path: { status_id: status.id },
          query: { version: status.version, replace_with: replaceWith },
        },
      }),
    ),
  )
}
