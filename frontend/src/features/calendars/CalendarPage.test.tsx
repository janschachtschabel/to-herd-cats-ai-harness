import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { viewerZone } from '@/features/automations/zoned'
import { apiError, type Call, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeCalendar, makeOccurrence } from '@/test/calendars'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { dayStart } from './dates'

const SPACE_ID = '0190a2b3-c4d5-7e6f-8a9b-0c1d2e3f4a5b'
const mine = makeSpace({ id: 'space-me', name: 'Ich', kind: 'personal', my_role: 'admin' })
const team = makeSpace({ id: SPACE_ID, name: 'Projekt Apfel', my_role: 'editor' })
const open = makeSpace({ id: 'space-open', name: 'Handbuch', kind: 'open', my_role: 'viewer' })
const own = makeCalendar({ id: 'cal-me', space_id: 'space-me', name: null, is_default: true })
const apfel = makeCalendar({ id: 'cal-team', space_id: SPACE_ID, name: 'Apfel', color: 'green' })
const manual = makeCalendar({ id: 'cal-open', space_id: 'space-open', name: 'Termine' })

type Window = (call: Call) => unknown

function calendarApi(window: Window, extra: Record<string, unknown> = {}) {
  return mockApi({
    ...shellRoutes(makeMe([]), [mine, team, open]),
    'GET /api/calendars': page([own, apfel, manual]),
    'GET /api/calendar/events': window,
    ...extra,
  })
}

const meeting = makeOccurrence({ title: 'Teamrunde', calendar_id: 'cal-team' })

describe('calendar page', () => {
  test('asks the month’s window in the viewer’s zone and loads its pages one after another', async () => {
    const api = calendarApi((call) =>
      call.query.get('cursor') === 'p2'
        ? page([
            makeOccurrence({
              title: 'Nachzügler',
              start: '2026-11-25T09:00:00Z',
              end: '2026-11-25T10:00:00Z',
            }),
          ])
        : page([meeting], 'p2'),
    )
    await renderApp('/calendar?date=2026-11-19')
    expect(await screen.findByRole('button', { name: /Teamrunde/ })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Nachzügler/ })).toBeInTheDocument()
    const [first, second] = api.find('GET', '/api/calendar/events')
    const zone = viewerZone()
    expect(first!.query.get('time_zone')).toBe(zone)
    expect(first!.query.get('from')).toBe(dayStart('2026-10-26', zone))
    expect(first!.query.get('to')).toBe(dayStart('2026-12-07', zone))
    expect(first!.query.get('calendar_ids')).toBeNull()
    expect(second!.query.get('cursor')).toBe('p2')
    expect(screen.getByRole('grid', { name: 'November 2026' })).toBeInTheDocument()
  })

  test('the list groups calendars by space, words defaults and marks what one only reads', async () => {
    calendarApi(() => page([]))
    await renderApp('/calendar?date=2026-11-19')
    const list = await screen.findByRole('region', { name: 'Kalender' })
    const personal = within(list).getByRole('group', { name: 'Ich' })
    expect(await within(personal).findByRole('checkbox', { name: 'Mein Kalender' })).toBeChecked()
    const editor = within(list).getByRole('group', { name: 'Projekt Apfel' })
    expect(within(editor).getByRole('checkbox', { name: 'Apfel' })).toBeInTheDocument()
    // `my_role` viewer: calendar.read alone.
    const viewer = within(list).getByRole('group', { name: 'Handbuch' })
    expect(within(viewer).getByRole('checkbox', { name: 'Termine nur lesen' })).toBeInTheDocument()
    expect(await screen.findByText('Keine Termine in diesem Zeitraum.')).toBeInTheDocument()
  })

  test('hiding a calendar asks the window for the others only', async () => {
    const api = calendarApi(() => page([meeting]))
    const { user } = await renderApp('/calendar?date=2026-11-19')
    await user.click(await screen.findByRole('checkbox', { name: 'Apfel' }))
    await waitFor(() =>
      expect(api.find('GET', '/api/calendar/events').at(-1)!.query.getAll('calendar_ids')).toEqual([
        'cal-me',
        'cal-open',
      ]),
    )
    await waitFor(() => expect(screen.queryByRole('button', { name: /Teamrunde/ })).toBeNull())
    expect(JSON.parse(localStorage.getItem('herd.calendars.hidden')!)).toEqual(['cal-team'])
  })

  test('a loading window shows that it loads', async () => {
    calendarApi(() => new Promise(() => {}))
    await renderApp('/calendar?date=2026-11-19')
    expect(await screen.findByRole('status', { name: 'Wird geladen …' })).toBeInTheDocument()
  })

  test('a failed window offers to try again', async () => {
    let fail = true
    calendarApi(() => (fail ? apiError(500, 'internal') : page([meeting])))
    const { user } = await renderApp('/calendar?date=2026-11-19')
    const retry = await screen.findByRole('button', { name: 'Erneut versuchen' })
    fail = false
    await user.click(retry)
    expect(await screen.findByRole('button', { name: /Teamrunde/ })).toBeInTheDocument()
  })

  test('a window beyond 2,000 occurrences says what to do and keeps what it loaded', async () => {
    calendarApi((call) =>
      call.query.get('cursor') ? apiError(422, 'calendar.window_too_dense') : page([meeting], 'p2'),
    )
    await renderApp('/calendar?date=2026-11-19')
    expect(await screen.findByText(/zu viele Termine/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Teamrunde/ })).toBeInTheDocument()
  })

  test('views and steps go into the address; a day opens from the month', async () => {
    const api = calendarApi(() => page([meeting]))
    const { router, user } = await renderApp('/calendar?date=2026-11-19')
    await user.click(await screen.findByRole('button', { name: 'Woche' }))
    await waitFor(() => expect(router.state.location.search).toMatchObject({ view: 'week' }))
    expect(screen.getByRole('button', { name: 'Woche' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Nächster Zeitraum' }))
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ view: 'week', date: '2026-11-26' }),
    )
    const asked = api.find('GET', '/api/calendar/events').at(-1)!
    expect(asked.query.get('from')).toBe(dayStart('2026-11-23', viewerZone()))
    await user.click(screen.getByRole('button', { name: 'Monat' }))
    await user.click(await screen.findByRole('gridcell', { name: /26\. November 2026/ }))
    await user.keyboard('{Enter}')
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ view: 'day', date: '2026-11-26' }),
    )
  })

  test('an event opens read-only; a redacted one says only „Belegt“', async () => {
    const hidden = makeOccurrence({
      title: null,
      redacted: true,
      calendar_id: 'cal-team',
      start: '2026-11-20T09:00:00Z',
      end: '2026-11-20T10:00:00Z',
    })
    calendarApi(() => page([meeting, hidden]))
    const { user } = await renderApp('/calendar?date=2026-11-19&view=agenda')
    await user.click(await screen.findByRole('button', { name: /Belegt/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Belegt' })
    expect(within(dialog).getByText('Du siehst diesen Termin nur als belegt.')).toBeInTheDocument()
    expect(within(dialog).getByText('Apfel')).toBeInTheDocument()
  })

  test('the named way: one space’s calendars and events', async () => {
    const api = calendarApi(() => page([meeting]), {
      'GET /api/spaces/:id': team,
      'GET /api/spaces/:id/calendars': page([apfel]),
    })
    await renderApp(`/calendar?space=${SPACE_ID}&date=2026-11-19`)
    expect(
      await screen.findByRole('heading', { name: 'Kalender im Bereich Projekt Apfel' }),
    ).toBeInTheDocument()
    await screen.findByRole('button', { name: /Teamrunde/ })
    expect(api.find('GET', `/api/spaces/${SPACE_ID}/calendars`)).toHaveLength(1)
    expect(api.find('GET', '/api/calendars')).toHaveLength(0)
    expect(api.find('GET', '/api/calendar/events')[0]!.query.get('space_id')).toBe(SPACE_ID)
    expect(screen.getByRole('link', { name: 'Alle meine Kalender' })).toBeInTheDocument()
  })

  test('the sidebar leads to the calendar', async () => {
    calendarApi(() => page([]))
    const { router, user } = await renderApp('/spaces')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    await user.click(within(nav).getByRole('link', { name: 'Kalender' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/calendar'))
  })
})
