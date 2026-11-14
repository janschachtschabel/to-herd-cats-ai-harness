import { useDroppable } from '@dnd-kit/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { Schemas } from '@/lib/api'
import { cn } from '@/lib/utils'
import { CATEGORY_DOT } from '../display'
import type { MoveMyCard, MyCardFocus } from './dnd'
import { MyCard } from './MyCard'
import { useMyColumnMore } from './queries'

/** A category as a column of my board: its name and count, its cards in board order
 *  (priority, due day, number), more on request. A drop target. */
export function MyColumn({
  column,
  movable,
  onMove,
  focus,
  onFocused,
}: {
  column: Schemas['MyColumnOut']
  movable: (spaceId: string) => boolean
  onMove: MoveMyCard
  focus: MyCardFocus | null
  onFocused: () => void
}) {
  const { t } = useTranslation()
  const { setNodeRef, isOver } = useDroppable({ id: column.category })
  const [wanted, setWanted] = useState(false)
  const more = useMyColumnMore(column.category, column.next_cursor, wanted)
  const shown = column.items.map((item) => item.id)
  const cards = [...column.items, ...more.items.filter((item) => !shown.includes(item.id))]
  const headingId = `my-column-${column.category}`
  return (
    <section
      ref={setNodeRef}
      aria-labelledby={headingId}
      className={cn(
        'flex w-72 shrink-0 flex-col gap-2 rounded-lg bg-muted/50 p-2',
        isOver && 'ring-2 ring-ring',
      )}
    >
      <h2 id={headingId} className="flex items-center gap-2 px-1 text-sm font-semibold">
        <span aria-hidden className={cn('size-2 rounded-full', CATEGORY_DOT[column.category])} />
        <span className="truncate">{t(`tickets.categories.${column.category}`)}</span>
        <span className="ml-auto text-xs font-normal text-muted-foreground tabular-nums">
          <span aria-hidden>{column.count}</span>
          <span className="sr-only"> {t('tickets.board.count', { count: column.count })}</span>
        </span>
      </h2>
      <ul className="flex min-h-16 flex-col gap-2">
        {cards.map((ticket) => (
          <li key={ticket.id}>
            <MyCard
              ticket={ticket}
              movable={movable(ticket.space_id)}
              onMove={onMove}
              focus={
                focus?.ticketId === ticket.id && focus.category === ticket.status.category
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
