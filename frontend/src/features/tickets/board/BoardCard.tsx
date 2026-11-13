import { useDraggable } from '@dnd-kit/core'
import { Link } from '@tanstack/react-router'
import { GripVertical, MoreHorizontal } from 'lucide-react'
import { useEffect, useRef } from 'react'
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
import { AssigneeLabel, DueLabel, KindLabel, PriorityLabel } from '../parts'
import type { CardData, CardFocus, MoveCard } from './dnd'

/** A ticket on the board: key, title, kind, priority, assignee, due day. With
 *  `ticket.edit` it moves between columns by dragging (the whole card with a pointer;
 *  the grip with the keyboard: Space, arrows, Space) or through "change status". */
export function BoardCard({
  ticket,
  statuses,
  movable,
  onMove,
  focus,
  onFocused,
}: {
  ticket: TicketSummary
  statuses: Schemas['StatusRef'][]
  movable: boolean
  onMove: MoveCard
  /** Set once the card shows in the column it was moved to by keyboard or menu. */
  focus?: CardFocus['on']
  onFocused: () => void
}) {
  const { t } = useTranslation()
  const grip = useRef<HTMLButtonElement | null>(null)
  const menu = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    if (!focus) return
    ;(focus === 'grip' ? grip : menu).current?.focus()
    onFocused()
  }, [focus, onFocused])
  const data: CardData = { ticket }
  const { setNodeRef, setActivatorNodeRef, transform, isDragging, listeners, attributes } =
    useDraggable({ id: ticket.id, data, disabled: !movable })
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined
  return (
    <article
      ref={setNodeRef}
      style={style}
      aria-label={`${ticket.key} ${ticket.title}`}
      className={cn(
        'flex touch-manipulation flex-col gap-1.5 rounded-lg border bg-background p-2.5 shadow-xs',
        isDragging && 'relative z-10 shadow-lg ring-2 ring-ring',
      )}
      {...(movable ? listeners : {})}
    >
      <div className="flex items-start gap-1">
        {movable && (
          <button
            type="button"
            ref={(node) => {
              grip.current = node
              setActivatorNodeRef(node)
            }}
            {...attributes}
            aria-label={t('tickets.board.moveCard', { key: ticket.key })}
            className="-ml-1 cursor-grab rounded-sm p-0.5 text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <GripVertical className="size-4" aria-hidden />
          </button>
        )}
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
                ref={menu}
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
                onValueChange={(statusId) => onMove(ticket, statusId, 'menu')}
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
        <KindLabel kind={ticket.kind} />
        <PriorityLabel priority={ticket.priority} />
        <DueLabel due={ticket.due_on} />
      </div>
      <AssigneeLabel assignee={ticket.assignee} />
    </article>
  )
}
