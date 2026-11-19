import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { addDays, monthGrid, startOfWeek, type Day } from '../dates'
import { byStart, formatDay, formatMonth } from '../display'
import { byDay } from '../layout'
import type { Occurrence } from '../queries'
import { EventChip } from './EventChip'
import type { ViewProps } from './types'

/** How many events a day of the month shows before „+N weitere“. */
export const MAX_SHOWN = 3

const STEP: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }

/** The month as a grid (WAI-ARIA grid pattern): one day is the grid's tab stop; arrow
 *  keys move by day and week, Home and End to the week's ends, a step past the grid
 *  turns the month (`onAnchor`); Enter or Space opens the day (`onOpenDay`). Events
 *  are buttons for the pointer; from the keyboard a day opens them. */
export function MonthView({
  anchor,
  today,
  occurrences,
  calendars,
  zone,
  onOpen,
  onOpenDay,
  onAnchor,
}: ViewProps & {
  anchor: Day
  onOpenDay: (day: Day) => void
  onAnchor: (day: Day) => void
}) {
  const { i18n } = useTranslation()
  const locale = i18n.language
  const weeks = useMemo(() => monthGrid(anchor, locale), [anchor, locale])
  const days = useMemo(() => byDay(occurrences, zone, byStart), [occurrences, zone])
  const [focused, setFocused] = useState(anchor)
  const [shownAnchor, setShownAnchor] = useState(anchor)
  if (shownAnchor !== anchor) {
    setShownAnchor(anchor)
    setFocused(anchor)
  }
  const cells = useRef(new Map<Day, HTMLElement>())
  const moving = useRef(false)
  useEffect(() => {
    if (!moving.current) return
    moving.current = false
    cells.current.get(focused)?.focus()
  }, [focused, weeks])

  const first = weeks[0]![0]!
  const last = weeks.at(-1)!.at(-1)!
  const month = anchor.slice(0, 7)

  const move = (to: Day) => {
    moving.current = true
    if (to < first || to > last) onAnchor(to)
    else setFocused(to)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLElement>, day: Day) => {
    if (event.target !== event.currentTarget) return // a chip's own keys
    const step = STEP[event.key]
    if (step !== undefined) move(addDays(day, step))
    else if (event.key === 'Home') move(startOfWeek(day, locale))
    else if (event.key === 'End') move(addDays(startOfWeek(day, locale), 6))
    else if (event.key === 'Enter' || event.key === ' ') onOpenDay(day)
    else return
    event.preventDefault()
  }

  return (
    <div
      role="grid"
      aria-label={formatMonth(anchor, locale)}
      className="flex min-w-[42rem] flex-col rounded-lg border"
    >
      <div role="row" className="grid grid-cols-7 border-b bg-muted/40">
        {weeks[0]!.map((day) => (
          <div key={day} role="columnheader" className="px-2 py-1.5 text-xs font-medium">
            <span aria-hidden>{formatDay(day, locale, { weekday: 'short' })}</span>
            <span className="sr-only">{formatDay(day, locale, { weekday: 'long' })}</span>
          </div>
        ))}
      </div>
      {weeks.map((week) => (
        <div key={week[0]} role="row" className="grid grid-cols-7 border-b last:border-b-0">
          {week.map((day) => (
            <MonthCell
              key={day}
              day={day}
              outside={day.slice(0, 7) !== month}
              today={day === today}
              focusable={day === focused}
              occurrences={days.get(day) ?? []}
              register={(element) => {
                if (element) cells.current.set(day, element)
                else cells.current.delete(day)
              }}
              onKeyDown={(event) => onKeyDown(event, day)}
              onFocus={() => setFocused(day)}
              onOpenDay={onOpenDay}
              view={{ calendars, zone, onOpen }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

function MonthCell({
  day,
  outside,
  today,
  focusable,
  occurrences,
  register,
  onKeyDown,
  onFocus,
  onOpenDay,
  view,
}: {
  day: Day
  outside: boolean
  today: boolean
  focusable: boolean
  occurrences: Occurrence[]
  register: (element: HTMLElement | null) => void
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void
  onFocus: () => void
  onOpenDay: (day: Day) => void
  view: Pick<ViewProps, 'calendars' | 'zone' | 'onOpen'>
}) {
  const { t, i18n } = useTranslation()
  const shown = occurrences.slice(0, MAX_SHOWN)
  const more = occurrences.length - shown.length
  const name = formatDay(day, i18n.language)
  return (
    <div
      role="gridcell"
      ref={register}
      tabIndex={focusable ? 0 : -1}
      aria-current={today ? 'date' : undefined}
      onKeyDown={onKeyDown}
      onFocus={(event) => {
        if (event.target === event.currentTarget) onFocus()
      }}
      className="flex min-h-28 min-w-0 flex-col gap-0.5 border-r p-1 last:border-r-0 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset"
    >
      <span
        aria-hidden
        className={cn(
          'flex size-6 items-center justify-center self-end rounded-full text-xs tabular-nums',
          outside && 'text-muted-foreground',
          today && 'bg-primary font-semibold text-primary-foreground',
        )}
      >
        {Number(day.slice(8))}
      </span>
      <span className="sr-only">{name}</span>
      {shown.length > 0 && (
        <ul className="flex flex-col gap-0.5">
          {shown.map((occurrence) => (
            <li key={`${occurrence.event_id}/${occurrence.start}`}>
              <EventChip
                occurrence={occurrence}
                calendar={view.calendars.get(occurrence.calendar_id)}
                zone={view.zone}
                variant="line"
                onOpen={view.onOpen}
                tabIndex={-1}
              />
            </li>
          ))}
        </ul>
      )}
      {more > 0 && (
        <button
          type="button"
          tabIndex={-1}
          onClick={() => onOpenDay(day)}
          className="self-start rounded-sm px-1.5 text-xs font-medium hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {t('calendar.month.more', { count: more })}
          <span className="sr-only">
            {', '}
            {name}
          </span>
        </button>
      )}
    </div>
  )
}
