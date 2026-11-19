import { Link } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { viewerZone } from '@/features/automations/zoned'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { CalendarList } from './CalendarList'
import { rangeOf, shiftAnchor, todayIn, windowOf, type CalendarView, type Day } from './dates'
import { formatDay, formatDays, formatMonth } from './display'
import { EventPeek } from './EventPeek'
import { useCalendarSources } from './sources'
import { useWindow, type Occurrence } from './queries'
import type { CalendarSearch } from './search'
import { Toolbar } from './Toolbar'
import { AgendaView } from './views/AgendaView'
import { DayView } from './views/DayView'
import { MonthView } from './views/MonthView'
import { WeekView } from './views/WeekView'
import { useHiddenCalendars } from './visibility'

/** The most calendars the window takes by id (`calendar_ids`); beyond, the page asks
 *  without and leaves the hidden ones out itself. */
const MAX_CALENDAR_IDS = 100

/** The calendar (`/calendar`, plan M10 decision 17): the calendars of one's spaces, or
 *  with `space` one space's (the named way, audited for an admin outside it), in four
 *  views; view and day stand in the address. The server expands the series, judges
 *  sight and redacts; this page only shows what the window gives. */
export function CalendarPage({
  search,
  onSearch,
}: {
  search: CalendarSearch
  onSearch: (next: CalendarSearch) => void
}) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  const zone = useMemo(() => viewerZone(), [])
  const today = todayIn(zone)
  const view = search.view ?? 'month'
  const anchor = search.date ?? today
  const range = rangeOf(view, anchor, locale)
  const sources = useCalendarSources(search.space)
  const { hidden, toggle } = useHiddenCalendars()
  const [query, setQuery] = useState('')
  const q = useDebouncedValue(query.trim(), 300)
  const [opened, setOpened] = useState<Occurrence | null>(null)

  const listed = sources.calendars.items
  const shownIds = listed.filter((c) => !hidden.has(c.id)).map((c) => c.id)
  const anyHidden = shownIds.length < listed.length
  const waitForList = hidden.size > 0 && sources.calendars.isPending
  const events = useWindow(
    {
      ...windowOf(range, zone),
      timeZone: zone,
      calendarIds: waitForList
        ? []
        : anyHidden && shownIds.length <= MAX_CALENDAR_IDS
          ? shownIds
          : undefined,
      spaceId: search.space,
      q: q || undefined,
    },
    { everything: view !== 'agenda' },
  )
  const occurrences = useMemo(
    () => events.items.filter((o) => !hidden.has(o.calendar_id)),
    [events.items, hidden],
  )

  const go = (next: Partial<CalendarSearch>) => onSearch({ ...search, ...next })
  const openDay = (day: Day) => go({ view: 'day', date: day })
  const shared = { occurrences, calendars: sources.infos, zone, today, onOpen: setOpened }
  const allHidden = listed.length > 0 && shownIds.length === 0
  const loaded = !events.isPending && !events.isError && !events.hasMore
  const empty = loaded && occurrences.length === 0

  return (
    <div>
      <PageHeader
        title={
          sources.namedSpace
            ? t('calendar.named', { space: sources.namedSpace.name })
            : t('calendar.title')
        }
      >
        {search.space && (
          <Link
            to="/calendar"
            search={{ view: search.view, date: search.date }}
            className="text-sm underline"
          >
            {t('calendar.showAll')}
          </Link>
        )}
      </PageHeader>
      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="lg:w-56 lg:shrink-0">
          {sources.calendars.isPending ? (
            <LoadingState rows={3} />
          ) : sources.calendars.isError ? (
            <ErrorState error={sources.calendars.error} onRetry={sources.calendars.refetch} />
          ) : (
            <CalendarList groups={sources.groups} hidden={hidden} onToggle={toggle} />
          )}
        </aside>
        <div className="min-w-0 flex-1">
          <Toolbar
            view={view}
            title={periodTitle(view, anchor, range, locale)}
            query={query}
            onToday={() => go({ date: undefined })}
            onStep={(step) => go({ date: shiftAnchor(view, anchor, step) })}
            onView={(next) => go({ view: next })}
            onQuery={setQuery}
          />
          <div className="mb-2 min-h-5 text-sm text-muted-foreground" role="status">
            {allHidden
              ? t('calendar.window.hidden')
              : !events.isError && (events.loadingMore || (events.hasMore && view !== 'agenda'))
                ? t('calendar.window.loadingMore')
                : empty
                  ? t('calendar.window.empty')
                  : null}
          </div>
          {events.isError && (
            <div className="mb-3">
              <ErrorState error={events.error} onRetry={events.refetch} />
            </div>
          )}
          {events.isPending && !allHidden ? (
            <LoadingState />
          ) : (
            <div className="overflow-x-auto">
              {view === 'month' && (
                <MonthView
                  {...shared}
                  anchor={anchor}
                  onOpenDay={openDay}
                  onAnchor={(day) => go({ date: day })}
                />
              )}
              {view === 'week' && <WeekView {...shared} anchor={anchor} onOpenDay={openDay} />}
              {view === 'day' && <DayView {...shared} anchor={anchor} />}
              {view === 'agenda' && (
                <AgendaView
                  {...shared}
                  first={range.first}
                  last={range.last}
                  hasMore={events.hasMore && !events.isError}
                  loadingMore={events.loadingMore}
                  onLoadMore={events.loadMore}
                />
              )}
            </div>
          )}
        </div>
      </div>
      <EventPeek
        occurrence={opened}
        calendar={opened ? sources.infos.get(opened.calendar_id) : undefined}
        zone={zone}
        onClose={() => setOpened(null)}
      />
    </div>
  )
}

function periodTitle(
  view: CalendarView,
  anchor: Day,
  range: { first: Day; last: Day },
  locale: string,
): string {
  if (view === 'month') return formatMonth(anchor, locale)
  if (view === 'day') return formatDay(anchor, locale)
  return formatDays(range.first, range.last, locale)
}
