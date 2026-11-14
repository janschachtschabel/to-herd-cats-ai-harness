import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { BoardCell, BoardRow, Schemas, TicketSummary } from '@/lib/api'
import { cn } from '@/lib/utils'
import { CATEGORY_DOT } from '../display'
import { type BoardFilters, useColumnMore } from '../board/queries'
import { DailyCard } from './DailyCard'
import { changedSince } from './logic'

export interface DailyContext {
  spaceId: string
  filters: BoardFilters
  statuses: Schemas['StatusRef'][]
  since: string
  movable: boolean
  onMove: (ticket: TicketSummary, statusId: string) => void
}

/** A person's row of the daily view (`assignee` null: nobody's tickets): the name,
 *  which filters the board to them, how many tickets and how many changed, and a cell
 *  per status. */
export function DailyRow({
  row,
  focused,
  onFocus,
  context,
}: {
  row: BoardRow
  focused: boolean
  onFocus: (assignee: string) => void
  context: DailyContext
}) {
  const { t } = useTranslation()
  const name = row.assignee
    ? (row.assignee.name ?? t('tickets.fields.unknownPerson'))
    : t('tickets.daily.unassigned')
  const id = `daily-row-${row.assignee?.id ?? 'none'}`
  const count = row.cells.reduce((sum, cell) => sum + cell.count, 0)
  const changed = row.cells.reduce((sum, cell) => sum + cell.changed, 0)
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2 border-t pt-3">
      <div className="sticky left-0 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {focused ? (
          <h3 id={id} className="text-sm font-semibold">
            {name}
          </h3>
        ) : (
          <h3 className="text-sm font-semibold">
            <button
              type="button"
              aria-label={
                row.assignee
                  ? t('tickets.daily.focus', { name })
                  : t('tickets.daily.focusUnassigned')
              }
              onClick={() => onFocus(row.assignee?.id ?? 'none')}
              className="rounded-sm hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span id={id}>{name}</span>
            </button>
          </h3>
        )}
        <span className="text-xs text-muted-foreground">
          {t('tickets.daily.summary', { count, changed })}
        </span>
      </div>
      <div className="grid auto-cols-[16rem] grid-flow-col gap-3">
        {row.cells.map((cell) => (
          <DailyCell key={cell.status_id} cell={cell} person={name} row={row} context={context} />
        ))}
      </div>
    </section>
  )
}

function DailyCell({
  cell,
  person,
  row,
  context,
}: {
  cell: BoardCell
  person: string
  row: BoardRow
  context: DailyContext
}) {
  const { t } = useTranslation()
  const status = context.statuses.find((s) => s.id === cell.status_id)
  const [wanted, setWanted] = useState(false)
  const more = useColumnMore(
    context.spaceId,
    cell.status_id,
    { ...context.filters, assignee: row.assignee?.id ?? 'none' },
    cell.next_cursor,
    wanted,
  )
  const shown = new Set(cell.items.map((item) => item.id))
  const cards = [
    ...cell.items.map((item) => ({ ticket: item as TicketSummary, changed: item.changed })),
    ...more.items
      .filter((item) => !shown.has(item.id))
      .map((item) => ({ ticket: item, changed: changedSince(item, context.since) })),
  ]
  return (
    <div
      role="group"
      aria-label={t('tickets.daily.cell', { person, status: status?.name ?? '' })}
      className="flex flex-col gap-2 rounded-lg bg-muted/50 p-2"
    >
      <p className="flex items-center gap-2 px-1 text-xs font-medium">
        {status && (
          <span aria-hidden className={cn('size-2 rounded-full', CATEGORY_DOT[status.category])} />
        )}
        <span className="truncate">{status?.name}</span>
        <span className="ml-auto flex items-center gap-2 text-muted-foreground tabular-nums">
          {cell.changed > 0 && (
            <span className="text-amber-800 dark:text-amber-300">
              {t('tickets.daily.cellChanged', { count: cell.changed })}
            </span>
          )}
          <span aria-hidden>{cell.count}</span>
          <span className="sr-only">{t('tickets.board.count', { count: cell.count })}</span>
        </span>
      </p>
      <ul className="flex flex-col gap-2">
        {cards.map(({ ticket, changed }) => (
          <li key={ticket.id}>
            <DailyCard
              ticket={ticket}
              changed={changed}
              statuses={context.statuses}
              movable={context.movable}
              onMove={context.onMove}
            />
          </li>
        ))}
      </ul>
      {cards.length < cell.count && more.hasMore && (
        <Button
          variant="ghost"
          size="sm"
          disabled={more.loading}
          onClick={() => (wanted ? more.loadMore() : setWanted(true))}
        >
          {more.loading ? t('states.loadingMore') : t('actions.loadMore')}
        </Button>
      )}
    </div>
  )
}
