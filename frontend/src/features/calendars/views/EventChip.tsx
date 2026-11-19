import type { CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { eventTitle, startTime, timeRange, TONE_EDGE, type CalendarInfo } from '../display'
import type { Occurrence } from '../queries'

/** One occurrence as a button with its full name (title or „Belegt“, time, calendar;
 *  WCAG 2.2: the visible text starts the name). `line`: one line with the start time
 *  (month, all-day row); `block`: a box in the time grid with title and times. */
export function EventChip({
  occurrence,
  calendar,
  zone,
  variant,
  onOpen,
  tabIndex,
  style,
}: {
  occurrence: Occurrence
  calendar: CalendarInfo | undefined
  zone: string
  variant: 'line' | 'block'
  onOpen: (occurrence: Occurrence) => void
  tabIndex?: number
  style?: CSSProperties
}) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  const title = eventTitle(t, occurrence)
  const range = timeRange(t, occurrence, zone, locale)
  const cancelled = occurrence.status === 'cancelled'
  const calendarLabel = calendar?.label ?? t('calendar.list.unknownSpace')
  // The block shows its times; the line only the start, so its name adds the range.
  const details =
    variant === 'line'
      ? t('calendar.event.details', { time: range, calendar: calendarLabel })
      : calendarLabel
  const shownTime = occurrence.all_day ? null : startTime(occurrence, zone, locale)
  return (
    <button
      type="button"
      tabIndex={tabIndex}
      style={style}
      data-redacted={occurrence.redacted || undefined}
      onClick={(event) => {
        event.stopPropagation()
        onOpen(occurrence)
      }}
      className={cn(
        'w-full min-w-0 overflow-hidden rounded-sm border-l-4 bg-muted text-left text-xs text-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        calendar ? TONE_EDGE[calendar.color] : 'border-l-border',
        variant === 'line'
          ? 'flex items-center gap-1 truncate px-1.5 py-0.5'
          : 'h-full px-1.5 py-1',
        occurrence.redacted && 'italic',
        cancelled && 'line-through',
      )}
    >
      {variant === 'line' ? (
        <>
          {shownTime && <span className="shrink-0 tabular-nums">{shownTime}</span>}{' '}
          <span className="truncate font-medium">{title}</span>
        </>
      ) : (
        <>
          <span className="block truncate font-medium">{title}</span>{' '}
          <span className="block truncate tabular-nums">{range}</span>
        </>
      )}
      <span className="sr-only">
        {', '}
        {details}
        {cancelled && `, ${t('calendar.event.cancelled')}`}
      </span>
    </button>
  )
}
