import { useTranslation } from 'react-i18next'
import { ErrorState, LoadingState } from '@/features/shared/states'
import type { Ticket } from '@/lib/api'
import { childTotal } from './display'
import { Progress } from './Progress'
import { useChildren } from './queries'
import { TicketRows } from './TicketRows'

/** The tickets under this one, with how far they are. Nothing while it has none. */
export function TicketChildren({ ticket }: { ticket: Ticket }) {
  const { t } = useTranslation()
  const total = childTotal(ticket.children)
  const children = useChildren(ticket.id, total > 0)
  if (total === 0) return null
  return (
    <section aria-labelledby="ticket-children" className="flex flex-col gap-2">
      <h2 id="ticket-children" className="text-sm font-semibold">
        {t('tickets.view.children', { count: total })}
      </h2>
      <Progress counts={ticket.children} />
      {children.isPending ? (
        <LoadingState rows={2} />
      ) : children.isError ? (
        <ErrorState error={children.error} onRetry={() => void children.refetch()} />
      ) : (
        <TicketRows tickets={children.data.items} />
      )}
    </section>
  )
}
