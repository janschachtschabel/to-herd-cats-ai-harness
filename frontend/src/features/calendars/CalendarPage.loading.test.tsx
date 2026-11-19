import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, test } from 'vitest'
import { createQueryClient } from '@/app/queryClient'
import { apiError, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeCalendar, makeOccurrence } from '@/test/calendars'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { useWindow } from './queries'

const me = makeMe([], { id: 'user-me' })
const mine = makeSpace({
  id: 'space-me',
  name: 'Mia Muster',
  kind: 'personal',
  owner_user_id: 'user-me',
  my_role: 'admin',
})
const own = makeCalendar({ id: 'cal-me', space_id: 'space-me', name: null, is_default: true })
const meeting = makeOccurrence({ title: 'Teamrunde', calendar_id: 'cal-me' })

beforeEach(() => localStorage.clear())

describe('calendar page while things load', () => {
  test('the next window loads quietly: the grid stays, the status says it loads', async () => {
    mockApi({
      ...shellRoutes(me, [mine]),
      'GET /api/calendars': page([own]),
      'GET /api/calendar/events': (call: { query: URLSearchParams }) =>
        call.query.get('from')!.startsWith('2026-10') ? page([meeting]) : new Promise(() => {}),
    })
    const { user } = await renderApp('/calendar?date=2026-11-19')
    expect(await screen.findByRole('button', { name: /Teamrunde/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Nächster Zeitraum' }))
    expect(await screen.findByRole('grid', { name: 'Dezember 2026' })).toBeInTheDocument()
    expect(screen.getByText('Wird geladen …')).toBeInTheDocument()
    expect(screen.queryByText('Keine Termine in diesem Zeitraum.')).toBeNull()
  })

  test('a failed calendar list says so and offers to try again', async () => {
    let fail = true
    mockApi({
      ...shellRoutes(me, [mine]),
      'GET /api/calendars': () => (fail ? apiError(500, 'internal') : page([own])),
      'GET /api/calendar/events': page([]),
    })
    const { user } = await renderApp('/calendar?date=2026-11-19')
    const retry = await screen.findByRole('button', { name: 'Erneut versuchen' })
    fail = false
    await user.click(retry)
    expect(await screen.findByRole('checkbox', { name: 'Mein Kalender' })).toBeInTheDocument()
  })

  // The page's own question for the spaces' names (the sidebar asks without the flag).
  const calendarSpaces = (reply: () => unknown) => (call: { query: URLSearchParams }) =>
    call.query.get('include_others_personal') === 'false' ? reply() : page([mine])

  test('while the spaces load the list waits instead of guessing names', async () => {
    mockApi({
      ...shellRoutes(me, [mine]),
      'GET /api/spaces': calendarSpaces(() => new Promise(() => {})),
      'GET /api/calendars': page([own]),
      'GET /api/calendar/events': page([]),
    })
    await renderApp('/calendar?date=2026-11-19')
    await screen.findByRole('grid', { name: 'November 2026' })
    expect(screen.getAllByRole('status', { name: 'Wird geladen …' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('region', { name: 'Kalender' })).toBeNull()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  test('failed spaces show their error with a retry and no guessed names', async () => {
    let fail = true
    mockApi({
      ...shellRoutes(me, [mine]),
      'GET /api/spaces': calendarSpaces(() => (fail ? apiError(500, 'internal') : page([mine]))),
      'GET /api/calendars': page([own]),
      'GET /api/calendar/events': page([]),
    })
    const { user } = await renderApp('/calendar?date=2026-11-19')
    const list = await screen.findByRole('group', { name: 'Bereich (Name nicht geladen)' })
    expect(within(list).getByRole('checkbox', { name: 'Standardkalender' })).toBeInTheDocument()
    expect(screen.queryByText('nur lesen')).toBeNull()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByRole('checkbox', { name: 'Mein Kalender' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Mein Bereich' })).toBeInTheDocument()
  })
})

describe('calendar queries and refusals', () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
  let client = createQueryClient()
  beforeEach(() => {
    client = createQueryClient()
    // The app's own default (`retry: 1`), without the wait between tries.
    client.setDefaultOptions({ queries: { retry: 1, retryDelay: 0 } })
  })
  const params = {
    from: '2026-11-01T00:00:00Z',
    to: '2026-12-01T00:00:00Z',
    timeZone: 'UTC',
  }

  test('a refused window (422) is asked once', async () => {
    const api = mockApi({
      'GET /api/calendar/events': () => apiError(422, 'calendar.window_too_dense'),
    })
    const { result } = renderHook(() => useWindow(params), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(api.find('GET', '/api/calendar/events')).toHaveLength(1)
  })

  test('a window the server failed is asked once again', async () => {
    const api = mockApi({ 'GET /api/calendar/events': () => apiError(500, 'internal') })
    const { result } = renderHook(() => useWindow(params), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(api.find('GET', '/api/calendar/events')).toHaveLength(2)
  })
})
