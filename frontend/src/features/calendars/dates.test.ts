import { describe, expect, test } from 'vitest'
import {
  addDays,
  dayOf,
  dayStart,
  daysOf,
  monthGrid,
  rangeOf,
  shiftAnchor,
  todayIn,
  weekStart,
  windowOf,
} from './dates'

const timed = (start: string, end: string) => ({ start, end, all_day: false })
const allDay = (start: string, end: string) => ({ start, end, all_day: true })

describe('week start', () => {
  test('follows the language and its region', () => {
    expect(weekStart('de')).toBe(1) // Monday
    expect(weekStart('en')).toBe(7) // Sunday (en is en-US)
    expect(weekStart('en-GB')).toBe(1)
  })
})

describe('month grid', () => {
  test('whole weeks from the week start, across the turn of the year', () => {
    const grid = monthGrid('2026-12-01', 'de')
    expect(grid[0]![0]).toBe('2026-11-30') // a Monday
    expect(grid.at(-1)!.at(-1)).toBe('2027-01-03') // a Sunday
    expect(grid.every((week) => week.length === 7)).toBe(true)
    const sunday = monthGrid('2026-12-01', 'en')
    expect(sunday[0]![0]).toBe('2026-11-29')
    expect(sunday.at(-1)!.at(-1)).toBe('2027-01-02')
  })

  test('every day once, in order, over the clock change', () => {
    const days = monthGrid('2027-03-01', 'de').flat()
    expect(days).toContain('2027-03-28') // the change in Europe
    for (let i = 1; i < days.length; i++) expect(days[i]).toBe(addDays(days[i - 1]!, 1))
    expect(new Set(days).size).toBe(days.length)
  })
})

describe('days of an occurrence', () => {
  test('a timed one counts on the viewer’s day', () => {
    const late = timed('2026-11-20T23:30:00Z', '2026-11-21T00:30:00Z')
    expect(dayOf(late, 'UTC')).toBe('2026-11-20')
    expect(dayOf(late, 'Europe/Berlin')).toBe('2026-11-21')
    expect(daysOf(late, 'UTC')).toEqual(['2026-11-20', '2026-11-21'])
    expect(daysOf(late, 'Europe/Berlin')).toEqual(['2026-11-21'])
  })

  test('an event ending at midnight does not reach the next day', () => {
    expect(daysOf(timed('2026-11-20T22:00:00Z', '2026-11-21T00:00:00Z'), 'UTC')).toEqual([
      '2026-11-20',
    ])
  })

  test('an all-day one keeps its days in every zone', () => {
    const two = allDay('2026-11-20T00:00:00Z', '2026-11-22T00:00:00Z')
    for (const zone of ['UTC', 'America/Los_Angeles', 'Pacific/Kiritimati', 'Europe/Berlin']) {
      expect(dayOf(two, zone)).toBe('2026-11-20')
      expect(daysOf(two, zone)).toEqual(['2026-11-20', '2026-11-21'])
    }
  })
})

describe('the window of a view', () => {
  test('a day starts at the zone’s midnight, also on the day of the change', () => {
    expect(dayStart('2026-11-20', 'Europe/Berlin')).toBe('2026-11-19T23:00:00.000Z')
    expect(dayStart('2027-03-28', 'Europe/Berlin')).toBe('2027-03-27T23:00:00.000Z')
    // Midnight that the clock skips (Santiago, September 2026): the first valid time.
    expect(dayStart('2026-09-06', 'America/Santiago')).toBe('2026-09-06T04:00:00.000Z')
  })

  test('each view spans its days; the window runs from the first day to after the last', () => {
    expect(rangeOf('month', '2026-11-19', 'de')).toEqual({
      first: '2026-10-26',
      last: '2026-12-06',
    })
    expect(rangeOf('week', '2026-11-19', 'de')).toEqual({ first: '2026-11-16', last: '2026-11-22' })
    expect(rangeOf('week', '2026-11-19', 'en')).toEqual({ first: '2026-11-15', last: '2026-11-21' })
    expect(rangeOf('day', '2026-11-19', 'de')).toEqual({ first: '2026-11-19', last: '2026-11-19' })
    expect(rangeOf('agenda', '2026-11-19', 'de')).toEqual({
      first: '2026-11-19',
      last: '2026-12-18',
    })
    expect(windowOf({ first: '2026-11-19', last: '2026-11-19' }, 'Europe/Berlin')).toEqual({
      from: '2026-11-18T23:00:00.000Z',
      to: '2026-11-19T23:00:00.000Z',
    })
  })

  test('back and forth by the view’s step; today in the viewer’s zone', () => {
    expect(shiftAnchor('month', '2026-01-31', 1)).toBe('2026-02-01')
    expect(shiftAnchor('month', '2026-01-15', -1)).toBe('2025-12-01')
    expect(shiftAnchor('week', '2026-11-19', 1)).toBe('2026-11-26')
    expect(shiftAnchor('day', '2026-12-31', 1)).toBe('2027-01-01')
    expect(shiftAnchor('agenda', '2026-11-19', -1)).toBe('2026-10-20')
    const now = new Date('2026-11-19T23:30:00Z')
    expect(todayIn('UTC', now)).toBe('2026-11-19')
    expect(todayIn('Europe/Berlin', now)).toBe('2026-11-20')
  })
})
