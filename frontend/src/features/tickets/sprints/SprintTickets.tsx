import { Undo2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import type { Sprint } from '@/lib/api'
import { TicketRows } from '../TicketRows'
import { usePutIntoSprint, useSprintTickets } from './queries'

/** The tickets of a sprint, by priority. A closed sprint keeps only finished tickets
 *  (one reopened later goes back to the backlog); from a running or planned sprint an
 *  editor puts a ticket back into the backlog. */
export function SprintTickets({ sprint, editable }: { sprint: Sprint; editable: boolean }) {
  const { t } = useTranslation()
  const tickets = useSprintTickets(sprint.space_id, sprint.id)
  const put = usePutIntoSprint()
  const removable = editable && sprint.state !== 'closed'
  if (tickets.isPending) return <LoadingState rows={2} />
  if (tickets.isError)
    return <ErrorState error={tickets.error} onRetry={() => void tickets.refetch()} />
  if (tickets.items.length === 0)
    return <p className="text-xs text-muted-foreground">{t('tickets.sprints.noTickets')}</p>
  return (
    <div className="flex flex-col gap-2">
      {sprint.state === 'closed' && (
        <p className="text-xs text-muted-foreground">{t('tickets.sprints.closedNote')}</p>
      )}
      <SaveError error={put.data?.failed ? put.data.error : null} />
      {put.data?.stale ? (
        <p role="alert" className="text-sm">
          {t('tickets.sprints.removeStale')}
        </p>
      ) : null}
      <TicketRows
        tickets={tickets.items}
        action={(ticket) =>
          removable && (
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={put.isPending}
              aria-label={t('tickets.sprints.removeTicket', { key: ticket.key })}
              title={t('tickets.sprints.removeTicket', { key: ticket.key })}
              onClick={() => put.mutate({ tickets: [ticket], sprintId: null })}
            >
              <Undo2 aria-hidden />
            </Button>
          )
        }
      />
      <LoadMore hasMore={tickets.hasMore} loading={tickets.loadingMore} onLoad={tickets.loadMore} />
    </div>
  )
}
