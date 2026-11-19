import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, test, vi } from 'vitest'
import { calendarInfos, makeOccurrence } from '@/test/calendars'
import { AgendaView } from './AgendaView'

function agenda(occurrences: ReturnType<typeof makeOccurrence>[], hasMore = false) {
  const props = {
    first: '2026-11-19',
    last: '2026-12-18',
    today: '2026-11-19',
    occurrences,
    calendars: calendarInfos(),
    zone: 'UTC',
    onOpen: vi.fn(),
    hasMore,
    loadingMore: false,
    onLoadMore: vi.fn(),
  }
  render(<AgendaView {...props} />)
  return { ...props, user: userEvent.setup() }
}

describe('agenda', () => {
  test('days with events as headings, their events below in order', () => {
    agenda([
      makeOccurrence({
        title: 'Später',
        start: '2026-11-20T15:00:00Z',
        end: '2026-11-20T16:00:00Z',
      }),
      makeOccurrence({ title: 'Teamrunde' }),
      makeOccurrence({
        title: 'Geheim',
        redacted: true,
        start: '2026-11-20T08:00:00Z',
        end: '2026-11-20T09:00:00Z',
      }),
    ])
    const headings = screen.getAllByRole('heading', { level: 3 })
    expect(headings.map((h) => h.textContent)).toEqual([
      'Donnerstag, 19. November 2026',
      'Freitag, 20. November 2026',
    ])
    const friday = screen.getByRole('list', { name: 'Freitag, 20. November 2026' })
    const rows = within(friday).getAllByRole('button')
    expect(rows[0]).toHaveTextContent(/^08:00–09:00 UhrBelegt/)
    expect(rows[1]).toHaveTextContent(/Später/)
    expect(screen.queryByText('Geheim')).toBeNull()
  })

  test('loads the next page on request', async () => {
    const view = agenda([makeOccurrence()], true)
    await view.user.click(screen.getByRole('button', { name: 'Weitere Termine laden' }))
    expect(view.onLoadMore).toHaveBeenCalled()
  })

  test('without a next page nothing more to load', () => {
    agenda([makeOccurrence()])
    expect(screen.queryByRole('button', { name: 'Weitere Termine laden' })).toBeNull()
  })

  test('an event before the first day shows only on the days it reaches', () => {
    agenda([
      makeOccurrence({
        title: 'Reise',
        all_day: true,
        start: '2026-11-18T00:00:00Z',
        end: '2026-11-20T00:00:00Z',
      }),
    ])
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Donnerstag, 19. November 2026',
    ])
  })

  test('an event of a calendar the list does not hold names it „Kalender“', () => {
    agenda([makeOccurrence({ title: 'Fremd', calendar_id: 'cal-foreign' })])
    expect(screen.getByRole('button', { name: /Fremd/ })).toHaveTextContent(/Kalender$/)
  })
})
