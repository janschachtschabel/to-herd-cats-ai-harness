import { describe, expect, test } from 'vitest'
import { calendarSearch } from './search'

describe('calendar address', () => {
  test('takes a space id, a view and a real day; refuses the rest', () => {
    const space = '0190A2B3-C4D5-7E6F-8A9B-0C1D2E3F4A5B'
    expect(calendarSearch({ space, view: 'week', date: '2026-11-19' })).toEqual({
      space: space.toLowerCase(),
      view: 'week',
      date: '2026-11-19',
    })
    expect(calendarSearch({ space: 'x', view: 'year', date: '2026-02-30' })).toEqual({
      space: undefined,
      view: undefined,
      date: undefined,
    })
    expect(calendarSearch({ date: '2400-01-01' }).date).toBeUndefined()
  })
})
