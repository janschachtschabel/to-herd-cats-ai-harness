/** Review of M10 Task 10: each test proves one finding (R10-n in
 *  .superpowers/sdd/m10/review-task-10.md) and fails until it is fixed. */
import { render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { apiError, type Call, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { calendarInfos, makeCalendar, makeOccurrence } from '@/test/calendars'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { MonthView } from './views/MonthView'
import { WeekView } from './views/WeekView'

const SPACE_ID = '0190a2b3-c4d5-7e6f-8a9b-0c1d2e3f4a5b'
const me = makeMe([], { id: 'user-me' })
const mine = makeSpace({
  id: 'space-me',
  name: 'Mia Muster',
  kind: 'personal',
  owner_user_id: 'user-me',
  my_role: 'admin',
})
const team = makeSpace({ id: SPACE_ID, name: 'Projekt Apfel', my_role: 'editor' })
const own = makeCalendar({ id: 'cal-me', space_id: 'space-me', name: null, is_default: true })
const apfel = makeCalendar({ id: 'cal-team', space_id: SPACE_ID, name: 'Apfel', color: 'green' })

function calendarApi(window: (call: Call) => unknown, extra: Record<string, unknown> = {}) {
  return mockApi({
    ...shellRoutes(me, [mine, team]),
    'GET /api/calendars': page([own, apfel]),
    'GET /api/calendar/events': window,
    ...extra,
  })
}

const viewProps = {
  today: '2026-11-18',
  calendars: calendarInfos(),
  zone: 'UTC',
  onOpen: vi.fn(),
  onOpenDay: vi.fn(),
}

beforeEach(() => localStorage.clear())

describe('review R10', () => {
  test('R10-1: an arrow key past the month’s edge keeps the keyboard in the grid', async () => {
    calendarApi(() => page([]))
    const { user } = await renderApp('/calendar?date=2026-11-01')
    const start = await screen.findByRole('gridcell', { name: /, 1\. November 2026/ })
    start.focus()
    await user.keyboard('{ArrowUp}')
    const grid = await screen.findByRole('grid', { name: 'Oktober 2026' })
    await waitFor(() =>
      expect(within(grid).getByRole('gridcell', { name: /25\. Oktober 2026/ })).toHaveFocus(),
    )
  })

  test('R10-2: while the calendars still load, the page does not say there are no events', async () => {
    localStorage.setItem('herd.calendars.hidden', JSON.stringify(['cal-team']))
    calendarApi(() => page([makeOccurrence({ calendar_id: 'cal-me' })]), {
      'GET /api/calendars': () => new Promise(() => {}),
    })
    await renderApp('/calendar?date=2026-11-19')
    await screen.findByRole('heading', { name: 'November 2026' })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByText('Keine Termine in diesem Zeitraum.')).toBeNull()
  })

  test('R10-3: an event over midnight does not show its start time on the day after', () => {
    const night = makeOccurrence({
      title: 'Nachtschicht',
      start: '2026-11-19T22:00:00Z',
      end: '2026-11-20T02:00:00Z',
    })
    render(
      <MonthView {...viewProps} anchor="2026-11-19" occurrences={[night]} onAnchor={vi.fn()} />,
    )
    const after = screen.getByRole('gridcell', { name: /20\. November 2026/ })
    const chip = within(after).getByRole('button', { name: /Nachtschicht/ })
    // On the 20th it reads "22:00 Nachtschicht": as if it began that evening.
    expect(chip.textContent).not.toMatch(/^22:00/)
  })

  test('R10-4: an all-day event of the week names its day to a screen reader', () => {
    const holiday = makeOccurrence({
      title: 'Betriebsausflug',
      all_day: true,
      start: '2026-11-18T00:00:00Z',
      end: '2026-11-19T00:00:00Z',
    })
    render(<WeekView {...viewProps} anchor="2026-11-19" occurrences={[holiday]} />)
    const chip = screen.getByRole('button', { name: /Betriebsausflug/ })
    const list = chip.closest('ul')!
    const named = `${chip.textContent} ${list.getAttribute('aria-label') ?? ''}`
    // Neither the button's name nor its list says which of the seven days it is on.
    expect(named).toMatch(/18\. November|Mittwoch/)
  })

  test('R10-5: without the spaces’ names the list does not word one’s own calendar as the general one', async () => {
    calendarApi(() => page([]), { 'GET /api/spaces': () => apiError(500, 'internal') })
    await renderApp('/calendar?date=2026-11-19')
    const list = await screen.findByRole('region', { name: 'Kalender' })
    await within(list).findByRole('checkbox', { name: /Apfel/ })
    // The personal default (name null) is worded from its space's kind; with the
    // spaces unknown it must not be called „Allgemein“ (and read-only) as if settled.
    expect(within(list).queryByRole('checkbox', { name: /Allgemein/ })).toBeNull()
  })

  test('R10-6: hiding one calendar keeps the events of calendars the list does not hold', async () => {
    // The window without `calendar_ids` also gives what one organises in a space one
    // is no member of (sight.listed_events_sql); the server filters by the ids sent.
    const foreign = makeOccurrence({ title: 'Fremdtermin', calendar_id: 'cal-foreign' })
    const meeting = makeOccurrence({ title: 'Teamrunde', calendar_id: 'cal-team' })
    const mineToo = makeOccurrence({ title: 'Eigenes', calendar_id: 'cal-me' })
    calendarApi((call) => {
      const ids = call.query.getAll('calendar_ids')
      const all = [foreign, meeting, mineToo]
      return page(ids.length ? all.filter((o) => ids.includes(o.calendar_id)) : all)
    })
    const { user } = await renderApp('/calendar?date=2026-11-19')
    expect(await screen.findByRole('button', { name: /Fremdtermin/ })).toBeInTheDocument()
    await user.click(await screen.findByRole('checkbox', { name: 'Apfel' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: /Teamrunde/ })).toBeNull())
    expect(await screen.findByRole('button', { name: /Eigenes/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Fremdtermin/ })).toBeInTheDocument()
  })

  test('R10-7: the look at an all-day event of several days names its last day too', async () => {
    const trip = makeOccurrence({
      title: 'Messe',
      calendar_id: 'cal-team',
      all_day: true,
      start: '2026-11-19T00:00:00Z',
      end: '2026-11-22T00:00:00Z',
    })
    calendarApi(() => page([trip]))
    const { user } = await renderApp('/calendar?date=2026-11-19&view=agenda')
    await user.click((await screen.findAllByRole('button', { name: /Messe/ }))[0]!)
    const dialog = await screen.findByRole('dialog', { name: 'Messe' })
    expect(dialog).toHaveTextContent(/21\. November/)
  })
})
