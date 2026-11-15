import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import type { TicketSummary } from '@/lib/api'
import { AssigneeLabel, DueLabel, KindLabel, PriorityLabel, StatusBadge } from './parts'
import { PickupBadge } from './PickupBadge'

/** Tickets as rows: key and title lead to the ticket; status, kind, priority, who and
 *  when below. `spaceNames` adds the space where the list spans several; `lead` a
 *  control at the start of each row (a checkbox), `action` one at its end. */
export function TicketRows({
  tickets,
  spaceNames,
  lead,
  action,
}: {
  tickets: TicketSummary[]
  spaceNames?: Map<string, string>
  lead?: (ticket: TicketSummary) => ReactNode
  action?: (ticket: TicketSummary) => ReactNode
}) {
  return (
    <ul className="flex flex-col divide-y rounded-lg border">
      {tickets.map((ticket) => (
        <li
          key={ticket.id}
          className="flex flex-col gap-1.5 p-3 sm:flex-row sm:items-center sm:gap-3"
        >
          <div className="flex min-w-0 flex-1 items-start gap-3">
            {lead && <div className="shrink-0 pt-0.5">{lead(ticket)}</div>}
            <div className="min-w-0 flex-1">
              <Link
                to="/tickets/$number"
                params={{ number: String(ticket.number) }}
                className="flex min-w-0 items-baseline gap-2 rounded-sm hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <span className="shrink-0 font-mono text-xs text-muted-foreground">
                  {ticket.key}
                </span>{' '}
                <span className="truncate text-sm font-medium">{ticket.title}</span>
              </Link>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                <KindLabel kind={ticket.kind} />
                <PriorityLabel priority={ticket.priority} />
                <AssigneeLabel assignee={ticket.assignee} />
                {ticket.awaiting_pickup && <PickupBadge />}
                <DueLabel due={ticket.due_on} />
                {spaceNames?.get(ticket.space_id) && (
                  <span className="truncate text-xs text-muted-foreground">
                    {spaceNames.get(ticket.space_id)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <StatusBadge status={ticket.status} />
            {action?.(ticket)}
          </div>
        </li>
      ))}
    </ul>
  )
}
