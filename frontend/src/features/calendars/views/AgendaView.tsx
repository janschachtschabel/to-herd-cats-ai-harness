import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Day } from '../dates'
import {
  byStart,
  eventTitle,
  formatDay,
  occurrenceKey,
  timeRange,
  TONE_DOT,
  type CalendarInfo,
} from '../display'
import { byDay } from '../layout'
import type { Occurrence } from '../queries'
import type { ViewProps } from './types'

/** The days from `first` to `last` that hold events, each a heading with its events
 *  in order; the window's next page comes on request (`onLoadMore`). */
export function AgendaView({
  first,
  last,
  today,
  occurrences,
  calendars,
  zone,
  onOpen,
  hasMore,
  loadingMore,
  onLoadMore,
}: ViewProps & {
  first: Day
  last: Day
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
}) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  const days = useMemo(() => {
    const grouped = byDay(occurrences, zone, byStart)
    return [...grouped.entries()]
      .filter(([day]) => day >= first && day <= last)
      .sort(([a], [b]) => a.localeCompare(b))
  }, [occurrences, zone, first, last])

  return (
    <div className="flex flex-col gap-4">
      {days.map(([day, list]) => {
        const name = formatDay(day, locale)
        return (
          <section key={day} aria-labelledby={`agenda-${day}`}>
            <h3
              id={`agenda-${day}`}
              aria-current={day === today ? 'date' : undefined}
              className={cn(
                'mb-1 border-b pb-1 text-sm font-semibold',
                day === today && 'text-primary',
              )}
            >
              {name}
            </h3>
            <ul aria-label={name} className="flex flex-col">
              {list.map((occurrence) => (
                <li key={occurrenceKey(occurrence)}>
                  <AgendaRow
                    occurrence={occurrence}
                    calendar={calendars.get(occurrence.calendar_id)}
                    time={timeRange(t, occurrence, zone, locale)}
                    onOpen={onOpen}
                  />
                </li>
              ))}
            </ul>
          </section>
        )
      })}
      {hasMore && (
        <Button
          variant="outline"
          className="self-center"
          disabled={loadingMore}
          onClick={onLoadMore}
        >
          {loadingMore ? t('states.loadingMore') : t('calendar.agenda.more')}
        </Button>
      )}
    </div>
  )
}

function AgendaRow({
  occurrence,
  calendar,
  time,
  onOpen,
}: {
  occurrence: Occurrence
  calendar: CalendarInfo | undefined
  time: string
  onOpen: (occurrence: Occurrence) => void
}) {
  const { t } = useTranslation()
  const cancelled = occurrence.status === 'cancelled'
  return (
    <button
      type="button"
      onClick={() => onOpen(occurrence)}
      className="flex w-full items-baseline gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <span className="w-36 shrink-0 tabular-nums">{time}</span>
      <span
        aria-hidden
        className={cn(
          'size-2 shrink-0 self-center rounded-full',
          calendar ? TONE_DOT[calendar.color] : 'bg-border',
        )}
      />
      <span
        className={cn(
          'min-w-0 flex-1 truncate font-medium',
          occurrence.redacted && 'italic',
          cancelled && 'line-through',
        )}
      >
        {eventTitle(t, occurrence)}
        {cancelled && <span className="sr-only">{`, ${t('calendar.event.cancelled')}`}</span>}
      </span>
      {occurrence.location && (
        <span className="hidden max-w-48 truncate text-muted-foreground sm:inline">
          {occurrence.location}
        </span>
      )}
      <span className="shrink-0 text-muted-foreground">{calendar?.label}</span>
    </button>
  )
}
