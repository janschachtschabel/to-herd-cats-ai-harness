import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState } from '@/features/shared/states'
import { ApiError } from '@/lib/api'
import { useTicket } from './queries'
import { TicketView } from './TicketView'

/** A ticket by its number (`/tickets/42`); `thread` and `message` open its discussion
 *  at a reply or mark a comment (from the activity or a search hit). A ticket one may
 *  not see is not there, the same as a number never given. */
export function TicketScreen({
  number,
  thread,
  message,
}: {
  number: number
  thread?: string
  message?: string
}) {
  const { t } = useTranslation()
  const ticket = useTicket(number)
  if (ticket.error instanceof ApiError && ticket.error.status === 404) {
    return (
      <EmptyState text={t('tickets.view.gone')}>
        <Button variant="outline" asChild>
          <Link to="/tickets">{t('tickets.view.toList')}</Link>
        </Button>
      </EmptyState>
    )
  }
  if (ticket.isPending) return <LoadingState />
  if (ticket.isError)
    return <ErrorState error={ticket.error} onRetry={() => void ticket.refetch()} />
  return <TicketView key={ticket.data.id} ticket={ticket.data} thread={thread} message={message} />
}
