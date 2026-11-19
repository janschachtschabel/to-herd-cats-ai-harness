import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, test, vi } from 'vitest'
import { calendarInfos, makeOccurrence } from '@/test/calendars'
import { DayView } from './DayView'
import { WeekView } from './WeekView'

function week(occurrences = [makeOccurrence()]) {
  const props = {
    anchor: '2026-11-19',
    today: '2026-11-19',
    occurrences,
    calendars: calendarInfos(),
    zone: 'UTC',
    onOpen: vi.fn(),
    onOpenDay: vi.fn(),
  }
  render(<WeekView {...props} />)
  return { ...props, user: userEvent.setup() }
}

describe('week view', () => {
  test('a redacted event shows „Belegt“ and never a title', async () => {
    const hidden = makeOccurrence({ title: 'Geheim', redacted: true, visibility: 'private' })
    const view = week([
      hidden,
      makeOccurrence({
        title: 'Planung',
        start: '2026-11-20T13:00:00Z',
        end: '2026-11-20T14:00:00Z',
      }),
    ])
    const busy = screen.getByRole('button', { name: /^Belegt 09:00–10:00 Uhr, Team$/ })
    expect(screen.queryByText('Geheim')).toBeNull()
    expect(screen.getByRole('button', { name: /^Planung/ })).toBeInTheDocument()
    await view.user.click(busy)
    expect(view.onOpen).toHaveBeenCalledWith(hidden)
  })

  test('seven days from the week start, each with its events; a day’s head opens it', async () => {
    const view = week([
      makeOccurrence({ title: 'Früh', start: '2026-11-16T08:00:00Z', end: '2026-11-16T09:00:00Z' }),
      makeOccurrence({
        title: 'Messe',
        all_day: true,
        start: '2026-11-21T00:00:00Z',
        end: '2026-11-23T00:00:00Z',
      }),
    ])
    const days = screen.getAllByRole('list', { name: /November 2026/ })
    expect(days).toHaveLength(7)
    expect(days[0]).toHaveAccessibleName('Montag, 16. November 2026')
    expect(within(days[0]!).getByRole('button', { name: /^Früh/ })).toBeInTheDocument()
    const allDay = screen.getByRole('group', { name: 'Ganztägig' })
    // Saturday and Sunday, the two days it lasts.
    expect(within(allDay).getAllByRole('button', { name: /^Messe, ganztägig/ })).toHaveLength(2)
    await view.user.click(
      screen.getByRole('button', { name: 'Donnerstag, 19. November 2026 öffnen' }),
    )
    expect(view.onOpenDay).toHaveBeenCalledWith('2026-11-19')
  })

  test('events at the same time stand side by side', () => {
    week([makeOccurrence({ title: 'A' }), makeOccurrence({ title: 'B' })])
    const a = screen.getByRole('button', { name: /^A / }).parentElement!
    const b = screen.getByRole('button', { name: /^B / }).parentElement!
    expect(a.style.width).toBe('50%')
    expect([a.style.left, b.style.left].sort()).toEqual(['0%', '50%'])
    expect(a.style.top).toBe(`${(9 / 24) * 100}%`)
  })
})

describe('day view', () => {
  test('one day, its events in time order', () => {
    render(
      <DayView
        anchor="2026-11-19"
        today="2026-11-19"
        occurrences={[
          makeOccurrence({
            title: 'Später',
            start: '2026-11-19T15:00:00Z',
            end: '2026-11-19T16:00:00Z',
          }),
          makeOccurrence({ title: 'Früher' }),
        ]}
        calendars={calendarInfos()}
        zone="UTC"
        onOpen={vi.fn()}
      />,
    )
    const day = screen.getByRole('list', { name: 'Donnerstag, 19. November 2026' })
    const names = within(day)
      .getAllByRole('button')
      .map((b) => b.textContent)
    expect(names[0]).toMatch(/^Früher/)
    expect(names[1]).toMatch(/^Später/)
  })
})
