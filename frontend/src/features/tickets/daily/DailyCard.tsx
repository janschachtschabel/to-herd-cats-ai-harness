import { Link } from '@tanstack/react-router'
import { MoreHorizontal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { Schemas, TicketSummary } from '@/lib/api'
import { cn } from '@/lib/utils'
import { DueLabel, KindLabel, PriorityLabel } from '../parts'

/** A ticket in the daily view: key, title, kind, priority, due day; marked when its
 *  status changed since the last working day. With `ticket.edit` its status changes
 *  through the menu (as on the board). */
export function DailyCard({
  ticket,
  changed,
  statuses,
  movable,
  onMove,
}: {
  ticket: TicketSummary
  changed: boolean
  statuses: Schemas['StatusRef'][]
  movable: boolean
  onMove: (ticket: TicketSummary, statusId: string) => void
}) {
  const { t } = useTranslation()
  return (
    <article
      aria-label={`${ticket.key} ${ticket.title}`}
      className={cn(
        'flex flex-col gap-1.5 rounded-lg border bg-background p-2.5 shadow-xs',
        changed && 'border-amber-500 ring-1 ring-amber-500/60 dark:border-amber-400',
      )}
    >
      <div className="flex items-start gap-1">
        <Link
          to="/tickets/$number"
          params={{ number: String(ticket.number) }}
          className="min-w-0 flex-1 rounded-sm text-sm hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <span className="font-mono text-xs text-muted-foreground">{ticket.key}</span>{' '}
          <span className="font-medium break-words">{ticket.title}</span>
        </Link>
        {movable && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label={t('tickets.board.changeStatus', { key: ticket.key })}
              >
                <MoreHorizontal aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>{t('tickets.board.statusMenu')}</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={ticket.status.id}
                onValueChange={(statusId) => onMove(ticket, statusId)}
              >
                {statuses.map((status) => (
                  <DropdownMenuRadioItem key={status.id} value={status.id}>
                    {status.name}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        {changed && (
          <span className="rounded-full bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-900 dark:bg-amber-950 dark:text-amber-200">
            {t('tickets.daily.changed')}
          </span>
        )}
        <KindLabel kind={ticket.kind} />
        <PriorityLabel priority={ticket.priority} />
        <DueLabel due={ticket.due_on} />
      </div>
    </article>
  )
}
