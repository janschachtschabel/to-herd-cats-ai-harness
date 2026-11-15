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
import type { MyCard as Card } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { StatusCategory } from '../display'
import { DueLabel, KindLabel, PriorityLabel, StatusBadge } from '../parts'
import type { MoveMyCard, MyCardData, MyCardFocus } from './dnd'
import { MY_CATEGORIES } from './queries'

/** A ticket of mine: key, title, its space and status, kind, priority, due day. Where
 *  `ticket.edit` holds in its space it moves between categories by dragging (the
 *  card with a pointer, the grip with the keyboard) or through "change column". */
export function MyCard({
  ticket,
  movable,
  onMove,
  focus,
  onFocused,
}: {
  ticket: Card
  movable: boolean
  onMove: MoveMyCard
  focus?: MyCardFocus['on']
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
  const data: MyCardData = { ticket }
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
                aria-label={t('tickets.myBoard.changeColumn', { key: ticket.key })}
              >
                <MoreHorizontal aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>{t('tickets.myBoard.columnMenu')}</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={ticket.status.category}
                onValueChange={(category) => onMove(ticket, category as StatusCategory, 'menu')}
              >
                {MY_CATEGORIES.map((category) => (
                  <DropdownMenuRadioItem key={category} value={category}>
                    {t(`tickets.categories.${category}`)}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="truncate text-xs font-medium text-muted-foreground">
          {ticket.space_name}
        </span>
        <StatusBadge status={ticket.status} />
      </div>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <KindLabel kind={ticket.kind} />
        <PriorityLabel priority={ticket.priority} />
        <DueLabel due={ticket.due_on} />
      </div>
    </article>
  )
}
