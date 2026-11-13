import { useDroppable } from '@dnd-kit/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { BoardColumn as Column, Schemas } from '@/lib/api'
import { cn } from '@/lib/utils'
import { CATEGORY_DOT } from '../display'
import { BoardCard } from './BoardCard'
import type { CardFocus, MoveCard } from './dnd'
import { type BoardFilters, useColumnMore } from './queries'

/** A status as a column: its name and how many tickets it holds, its cards in the fixed
 *  order (priority, due day, number), and more on request. A drop target. */
export function BoardColumn({
  spaceId,
  column,
  statuses,
  filters,
  movable,
  onMove,
  focus,
  onFocused,
}: {
  spaceId: string
  column: Column
  statuses: Schemas['StatusRef'][]
  filters: BoardFilters
  movable: boolean
  onMove: MoveCard
  focus: CardFocus | null
  onFocused: () => void
}) {
  const { t } = useTranslation()
  const { setNodeRef, isOver } = useDroppable({ id: column.status.id })
  const [wanted, setWanted] = useState(false)
  const more = useColumnMore(spaceId, column.status.id, filters, column.next_cursor, wanted)
  const shown = column.items.map((item) => item.id)
  const cards = [...column.items, ...more.items.filter((item) => !shown.includes(item.id))]
  const headingId = `column-${column.status.id}`
  return (
    <section
      ref={setNodeRef}
      aria-labelledby={headingId}
      className={cn(
        'flex w-72 shrink-0 flex-col gap-2 rounded-lg bg-muted/50 p-2',
        isOver && 'ring-2 ring-ring',
      )}
    >
      <h3 id={headingId} className="flex items-center gap-2 px-1 text-sm font-semibold">
        <span
          aria-hidden
          className={cn('size-2 rounded-full', CATEGORY_DOT[column.status.category])}
        />
        <span className="truncate">{column.status.name}</span>
        <span className="ml-auto text-xs font-normal text-muted-foreground tabular-nums">
          <span aria-hidden>{column.count}</span>
          <span className="sr-only"> {t('tickets.board.count', { count: column.count })}</span>
        </span>
      </h3>
      <ul className="flex min-h-16 flex-col gap-2">
        {cards.map((ticket) => (
          <li key={ticket.id}>
            <BoardCard
              ticket={ticket}
              statuses={statuses}
              movable={movable}
              onMove={onMove}
              focus={
                focus?.ticketId === ticket.id && focus.statusId === ticket.status.id
                  ? focus.on
                  : undefined
              }
              onFocused={onFocused}
            />
          </li>
        ))}
        {cards.length === 0 && (
          <li className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
            {t('tickets.board.emptyColumn')}
          </li>
        )}
      </ul>
      {cards.length < column.count && more.hasMore && (
        <Button
          variant="ghost"
          size="sm"
          disabled={more.loading}
          onClick={() => (wanted ? more.loadMore() : setWanted(true))}
        >
          {more.loading ? t('states.loadingMore') : t('actions.loadMore')}
        </Button>
      )}
    </section>
  )
}
