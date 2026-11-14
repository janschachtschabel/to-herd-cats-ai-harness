import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState } from '@/features/shared/states'
import type { TicketSummary } from '@/lib/api'
import type { BoardFilters } from '../board/queries'
import { DailyRow } from './DailyRow'
import { focusedPerson, formatWorkingDay } from './logic'
import { useDaily } from './queries'

/** The board for the daily (`group_by=assignee`): a row per person who has tickets
 *  here and one for nobody's, each cell a status with its count. What changed status
 *  since the last working day began is marked. A click on a person filters to them. */
export function DailyBoard({
  spaceId,
  filters,
  onFilters,
  movable,
  onMove,
}: {
  spaceId: string
  filters: BoardFilters
  onFilters: (next: BoardFilters) => void
  movable: boolean
  onMove: (ticket: TicketSummary, statusId: string) => void
}) {
  const { t, i18n } = useTranslation()
  const daily = useDaily(spaceId, filters)
  const focused = focusedPerson(filters)
  if (daily.isPending) return <LoadingState rows={3} />
  if (daily.isError) return <ErrorState error={daily.error} onRetry={() => void daily.refetch()} />
  const rows = daily.data.rows ?? []
  const since = daily.data.changed_since ?? new Date(0).toISOString()
  const statuses = daily.data.columns.map((column) => column.status)
  const focusName =
    focused === 'none'
      ? t('tickets.daily.unassigned')
      : (rows[0]?.assignee?.name ?? t('tickets.fields.unknownPerson'))
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        {t('tickets.daily.since', { day: formatWorkingDay(since, i18n.language) })}
      </p>
      {focused && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>{t('tickets.daily.focused', { name: focusName })}</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onFilters({ ...filters, assignee: undefined })}
          >
            <X aria-hidden />
            {t('tickets.daily.showAll')}
          </Button>
        </div>
      )}
      {daily.data.rows_truncated && (
        <p className="text-xs text-muted-foreground">{t('tickets.daily.truncated')}</p>
      )}
      {rows.length === 0 ? (
        <EmptyState text={t('tickets.daily.empty')} />
      ) : (
        <div className="-mx-1 overflow-x-auto px-1 pb-3">
          <div className="flex w-max min-w-full flex-col gap-3">
            <div
              className="grid auto-cols-[16rem] grid-flow-col gap-3 text-xs text-muted-foreground"
              aria-hidden
            >
              {daily.data.columns.map((column) => (
                <span key={column.status.id} className="truncate px-1">
                  {column.status.name} · {column.count}
                </span>
              ))}
            </div>
            {rows.map((row) => (
              <DailyRow
                key={row.assignee?.id ?? 'none'}
                row={row}
                focused={focused !== undefined}
                onFocus={(assignee) => onFilters({ ...filters, assignee })}
                context={{ spaceId, filters, statuses, since, movable, onMove }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
