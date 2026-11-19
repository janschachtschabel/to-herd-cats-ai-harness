import { useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import type { Day } from '../dates'
import { byStart, formatDay, occurrenceKey } from '../display'
import { byDay, columns, inAllDayRow, segmentOn } from '../layout'
import type { Occurrence } from '../queries'
import { EventChip } from './EventChip'
import type { ViewProps } from './types'

const HOUR_PX = 48
const MINUTES = 1440
/** The shortest box drawn, so a short event stays readable and clickable. */
const MIN_MINUTES = 20
/** Where the grid opens: the working day, not midnight. */
const FIRST_HOUR_SHOWN = 7

const HOURS = Array.from({ length: 24 }, (_, hour) => hour)

/** Days side by side with their hours (week and day view): an all-day row on top (all-day
 *  events and timed ones of a day or more), below each day's timed events as boxes in
 *  columns where they overlap (`layout.columns`). For screen readers each day is a list
 *  of its events in time order. */
export function TimeGrid({
  days,
  occurrences,
  calendars,
  zone,
  today,
  onOpen,
  onOpenDay,
}: ViewProps & { days: Day[]; onOpenDay?: ((day: Day) => void) | undefined }) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  const allDay = useMemo(
    () =>
      byDay(
        occurrences.filter((o) => inAllDayRow(o)),
        zone,
        byStart,
      ),
    [occurrences, zone],
  )
  const timed = useMemo(
    () =>
      byDay(
        occurrences.filter((o) => !inAllDayRow(o)),
        zone,
        byStart,
      ),
    [occurrences, zone],
  )
  const body = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (body.current) body.current.scrollTop = FIRST_HOUR_SHOWN * HOUR_PX - HOUR_PX / 4 // its label in sight
  }, [])
  const view = { calendars, zone, onOpen }
  const template = { gridTemplateColumns: `4rem repeat(${days.length}, minmax(0, 1fr))` }
  const hourLabel = (hour: number) =>
    new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(
      new Date(Date.UTC(2000, 0, 1, hour)),
    )

  return (
    <div className="flex min-w-[36rem] flex-col rounded-lg border">
      <div className="grid border-b bg-muted/40" style={template}>
        <span />
        {days.map((day) => (
          <DayHead key={day} day={day} today={day === today} onOpenDay={onOpenDay} />
        ))}
      </div>
      <div
        role="group"
        aria-label={t('calendar.week.allDay')}
        className="grid border-b"
        style={template}
      >
        <span aria-hidden className="px-1 py-1 text-right text-xs text-muted-foreground">
          {t('calendar.week.allDay')}
        </span>
        {days.map((day) => (
          <ul
            key={day}
            aria-label={t('calendar.week.allDayOf', { day: formatDay(day, locale) })}
            className="flex min-w-0 flex-col gap-0.5 border-l p-0.5"
          >
            {(allDay.get(day) ?? []).map((occurrence) => (
              <li key={occurrenceKey(occurrence)}>
                <EventChip
                  occurrence={occurrence}
                  variant="line"
                  day={day}
                  {...chipProps(view, occurrence)}
                />
              </li>
            ))}
          </ul>
        ))}
      </div>
      <div ref={body} className="max-h-[36rem] overflow-y-auto">
        <div className="relative grid" style={{ ...template, height: 24 * HOUR_PX }}>
          <div aria-hidden className="relative">
            {HOURS.map((hour) => (
              <span
                key={hour}
                className="absolute right-1 -translate-y-1/2 text-xs text-muted-foreground tabular-nums first:translate-y-0"
                style={{ top: hour * HOUR_PX }}
              >
                {hourLabel(hour)}
              </span>
            ))}
          </div>
          {days.map((day) => (
            <DayColumn
              key={day}
              day={day}
              label={formatDay(day, locale)}
              occurrences={timed.get(day) ?? []}
              view={view}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function chipProps(view: Pick<ViewProps, 'calendars' | 'zone' | 'onOpen'>, occurrence: Occurrence) {
  return {
    calendar: view.calendars.get(occurrence.calendar_id),
    zone: view.zone,
    onOpen: view.onOpen,
  }
}

function DayHead({
  day,
  today,
  onOpenDay,
}: {
  day: Day
  today: boolean
  onOpenDay: ((day: Day) => void) | undefined
}) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  const text = (
    <>
      <span aria-hidden>
        {formatDay(day, locale, { weekday: 'short' })}{' '}
        <span className={cn('tabular-nums', today && 'font-semibold text-primary')}>
          {Number(day.slice(8))}
        </span>
      </span>
    </>
  )
  const full = formatDay(day, locale)
  const className = 'border-l px-2 py-1.5 text-left text-xs font-medium'
  if (!onOpenDay)
    return (
      <div className={className} aria-current={today ? 'date' : undefined}>
        {text}
        <span className="sr-only">{full}</span>
      </div>
    )
  return (
    <button
      type="button"
      aria-current={today ? 'date' : undefined}
      onClick={() => onOpenDay(day)}
      className={cn(
        className,
        'hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset',
      )}
    >
      {text}
      <span className="sr-only">{t('calendar.week.openDay', { day: full })}</span>
    </button>
  )
}

function DayColumn({
  day,
  label,
  occurrences,
  view,
}: {
  day: Day
  label: string
  occurrences: Occurrence[]
  view: Pick<ViewProps, 'calendars' | 'zone' | 'onOpen'>
}) {
  const placed = useMemo(() => {
    const spans = occurrences.flatMap((occurrence) => {
      const span = segmentOn(occurrence, day, view.zone)
      if (!span) return []
      return [{ occurrence, start: span.start, end: Math.max(span.end, span.start + MIN_MINUTES) }]
    })
    return columns(spans)
  }, [occurrences, day, view.zone])
  return (
    <ul
      aria-label={label}
      className="relative border-l bg-[repeating-linear-gradient(to_bottom,transparent_0,transparent_47px,var(--border)_47px,var(--border)_48px)]"
    >
      {placed.map(({ item, column, columns: width }) => (
        <li
          key={occurrenceKey(item.occurrence)}
          className="absolute flex pr-0.5"
          style={{
            top: `${(item.start / MINUTES) * 100}%`,
            height: `${((Math.min(item.end, MINUTES) - item.start) / MINUTES) * 100}%`,
            left: `${(column / width) * 100}%`,
            width: `${100 / width}%`,
          }}
        >
          <EventChip
            occurrence={item.occurrence}
            variant="block"
            {...chipProps(view, item.occurrence)}
          />
        </li>
      ))}
    </ul>
  )
}
