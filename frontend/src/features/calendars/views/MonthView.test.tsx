import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, test, vi } from 'vitest'
import { calendarInfos, makeOccurrence } from '@/test/calendars'
import { MonthView } from './MonthView'

function month(occurrences = [makeOccurrence()]) {
  const props = {
    anchor: '2026-11-19',
    today: '2026-11-18',
    occurrences,
    calendars: calendarInfos(),
    zone: 'UTC',
    onOpen: vi.fn(),
    onOpenDay: vi.fn(),
    onAnchor: vi.fn(),
  }
  render(<MonthView {...props} />)
  return { ...props, user: userEvent.setup() }
}

const cell = (name: RegExp) => screen.getByRole('gridcell', { name })

describe('month view', () => {
  test('weeks from Monday; the chosen day is the one stop of the grid', () => {
    month()
    const grid = screen.getByRole('grid', { name: 'November 2026' })
    const heads = within(grid).getAllByRole('columnheader')
    expect(heads[0]).toHaveTextContent('Mo')
    expect(within(grid).getAllByRole('row')).toHaveLength(7) // the head and six weeks
    expect(cell(/19\. November 2026/)).toHaveAttribute('tabindex', '0')
    expect(cell(/20\. November 2026/)).toHaveAttribute('tabindex', '-1')
    expect(cell(/18\. November 2026/)).toHaveAttribute('aria-current', 'date')
  })

  test('arrow keys move by day and week, Enter opens the day', async () => {
    const view = month()
    cell(/19\. November 2026/).focus()
    await view.user.keyboard('{ArrowRight}')
    expect(cell(/20\. November 2026/)).toHaveFocus()
    await view.user.keyboard('{ArrowDown}')
    expect(cell(/27\. November 2026/)).toHaveFocus()
    await view.user.keyboard('{ArrowLeft}{ArrowUp}')
    expect(cell(/19\. November 2026/)).toHaveFocus()
    await view.user.keyboard('{Home}')
    expect(cell(/16\. November 2026/)).toHaveFocus()
    await view.user.keyboard('{End}')
    expect(cell(/22\. November 2026/)).toHaveFocus()
    await view.user.keyboard('{Enter}')
    expect(view.onOpenDay).toHaveBeenCalledWith('2026-11-22')
    expect(view.onAnchor).not.toHaveBeenCalled()
  })

  test('a step past the grid turns the month', async () => {
    const view = month()
    cell(/3\. Dezember 2026/).focus()
    await view.user.keyboard('{ArrowDown}')
    expect(view.onAnchor).toHaveBeenCalledWith('2026-12-10')
  })

  test('a full day shows three events and „+3 weitere“, which opens the day', async () => {
    const events = Array.from({ length: 6 }, (_, i) =>
      makeOccurrence({
        title: `Termin ${i + 1}`,
        start: `2026-11-19T0${i + 1}:00:00Z`,
        end: `2026-11-19T0${i + 1}:30:00Z`,
      }),
    )
    const view = month(events)
    const day = cell(/19\. November 2026/)
    expect(within(day).getAllByRole('button', { name: /^\d\d:\d\d Termin/ })).toHaveLength(3)
    expect(within(day).getByRole('button', { name: /Termin 1/ })).toBeInTheDocument()
    expect(within(day).queryByRole('button', { name: /Termin 4/ })).toBeNull()
    await view.user.click(within(day).getByRole('button', { name: /\+3 weitere/ }))
    expect(view.onOpenDay).toHaveBeenCalledWith('2026-11-19')
  })

  test('an event is a button with its full name; a click opens it', async () => {
    const meeting = makeOccurrence({ title: 'Teamrunde' })
    const view = month([meeting])
    const button = screen.getByRole('button', { name: '09:00 Teamrunde, 09:00–10:00 Uhr, Team' })
    await view.user.click(button)
    expect(view.onOpen).toHaveBeenCalledWith(meeting)
    expect(view.onOpenDay).not.toHaveBeenCalled()
  })

  test('an event over several days shows on each of them', () => {
    month([
      makeOccurrence({
        title: 'Klausur',
        all_day: true,
        start: '2026-11-19T00:00:00Z',
        end: '2026-11-21T00:00:00Z',
      }),
    ])
    for (const day of [/19\. November 2026/, /20\. November 2026/])
      expect(within(cell(day)).getByRole('button', { name: /Klausur, ganztägig/ })).toBeVisible()
    expect(within(cell(/21\. November 2026/)).queryByRole('button')).toBeNull()
  })
})
