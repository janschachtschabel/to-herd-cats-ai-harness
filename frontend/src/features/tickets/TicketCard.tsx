import { Link } from '@tanstack/react-router'
import { SquareKanban } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { AssigneeLabel, PriorityLabel, StatusBadge } from './parts'
import { useTicket } from './queries'
import { ticketRefs } from './refs'

/** One ticket a message names, as a small card that keeps itself current (live ticket
 *  events refresh it). The client loads it (plan M4, decision 9); a ticket one may not
 *  see answers 404, the same as a free number, and then nothing shows. */
export function TicketCard({ number }: { number: number }) {
  const { t } = useTranslation()
  const ticket = useTicket(number)
  if (!ticket.data) return null
  const { data } = ticket
  return (
    <Link
      to="/tickets/$number"
      params={{ number: String(number) }}
      aria-label={t('tickets.card.label', { key: data.key, title: data.title })}
      className="flex max-w-md flex-col gap-1 rounded-lg border bg-background p-2.5 text-sm hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <span className="flex min-w-0 items-center gap-1.5">
        <SquareKanban className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{data.key}</span>
        <span className="truncate font-medium">{data.title}</span>
      </span>
      <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <StatusBadge status={data.status} />
        <PriorityLabel priority={data.priority} />
        <AssigneeLabel assignee={data.assignee} />
      </span>
    </Link>
  )
}

/** The cards of a message: the tickets it names by key or link, at most three. */
export function TicketCards({ markdown }: { markdown: string }) {
  const numbers = useMemo(() => ticketRefs(markdown), [markdown])
  if (numbers.length === 0) return null
  return (
    <div className="mt-1.5 flex flex-col gap-1.5">
      {numbers.map((number) => (
        <TicketCard key={number} number={number} />
      ))}
    </div>
  )
}
