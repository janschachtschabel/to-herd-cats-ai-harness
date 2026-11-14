import { describe, expect, test } from 'vitest'
import { formatTerm, isoToZoned, zonedToIso } from './zoned'

describe('times in a zone', () => {
  test('a wall time in a zone becomes its instant', () => {
    expect(zonedToIso('2026-11-16', '09:00', 'Europe/Berlin')).toBe('2026-11-16T08:00:00.000Z')
    expect(zonedToIso('2026-07-01', '09:00', 'Europe/Berlin')).toBe('2026-07-01T07:00:00.000Z')
    expect(zonedToIso('2026-11-16', '09:00', 'America/New_York')).toBe('2026-11-16T14:00:00.000Z')
    expect(zonedToIso('2026-11-16', '09:00', 'UTC')).toBe('2026-11-16T09:00:00.000Z')
  })

  test('a wall time that the clock change skips moves on to the next valid one', () => {
    // 29 March 2026, 02:30 does not exist in Berlin (02:00 → 03:00).
    expect(zonedToIso('2026-03-29', '02:30', 'Europe/Berlin')).toBe('2026-03-29T01:30:00.000Z')
  })

  test('half-typed or unknown input gives nothing', () => {
    expect(zonedToIso('', '09:00', 'Europe/Berlin')).toBeNull()
    expect(zonedToIso('2026-11-16', '9', 'Europe/Berlin')).toBeNull()
    expect(zonedToIso('2026-11-16', '09:00', 'Mars/Olympus')).toBeNull()
  })

  test('an instant reads back as the wall time in a zone', () => {
    expect(isoToZoned('2026-11-16T08:00:00Z', 'Europe/Berlin')).toEqual({
      date: '2026-11-16',
      time: '09:00',
    })
    expect(isoToZoned('2026-11-16T03:30:00Z', 'America/New_York')).toEqual({
      date: '2026-11-15',
      time: '22:30',
    })
  })

  test("a term reads in the viewer's time and names the automation's zone", () => {
    const same = formatTerm('2026-11-16T08:00:00Z', 'de', 'Europe/Berlin', 'Europe/Berlin')
    expect(same).toEqual({ local: '16.11.2026, 09:00', there: null })
    const other = formatTerm('2026-11-16T14:00:00Z', 'de', 'Europe/Berlin', 'America/New_York')
    expect(other).toEqual({ local: '16.11.2026, 15:00', there: '09:00' })
    const none = formatTerm('2026-11-16T14:00:00Z', 'en', 'UTC', null)
    expect(none).toEqual({ local: 'Nov 16, 2026, 2:00 PM', there: null })
  })
})
