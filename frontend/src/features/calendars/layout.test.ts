import { describe, expect, test } from 'vitest'
import { columns, segmentOn } from './layout'

const at = (id: string, start: number, end: number) => ({ id, start, end })

function placed(items: ReturnType<typeof at>[]) {
  return Object.fromEntries(columns(items).map((p) => [p.item.id, [p.column, p.columns]]))
}

describe('columns of overlapping events', () => {
  test('events apart each take the whole width', () => {
    expect(placed([at('a', 540, 600), at('b', 660, 720)])).toEqual({ a: [0, 1], b: [0, 1] })
  })

  test('an event that ends when the next begins does not overlap it', () => {
    expect(placed([at('a', 540, 600), at('b', 600, 660)])).toEqual({ a: [0, 1], b: [0, 1] })
  })

  test('a chain of overlaps shares its columns; a freed column is taken again', () => {
    expect(placed([at('a', 540, 660), at('b', 600, 720), at('c', 660, 780)])).toEqual({
      a: [0, 2],
      b: [1, 2],
      c: [0, 2],
    })
  })

  test('three at once take three columns; a later one stands alone', () => {
    expect(
      placed([at('c', 540, 600), at('a', 540, 660), at('b', 570, 600), at('d', 700, 760)]),
    ).toEqual({ a: [0, 3], c: [1, 3], b: [2, 3], d: [0, 1] })
  })

  test('the same start: the longer goes first, then the given order', () => {
    expect(placed([at('short', 540, 570), at('long', 540, 720), at('same', 540, 570)])).toEqual({
      long: [0, 3],
      short: [1, 3],
      same: [2, 3],
    })
  })
})

describe('an occurrence on one day of the grid', () => {
  test('in wall minutes of the viewer’s zone, cut at the day’s bounds', () => {
    const night = { start: '2026-11-20T22:00:00Z', end: '2026-11-21T02:00:00Z', all_day: false }
    expect(segmentOn(night, '2026-11-20', 'UTC')).toEqual({ start: 1320, end: 1440 })
    expect(segmentOn(night, '2026-11-21', 'UTC')).toEqual({ start: 0, end: 120 })
    expect(segmentOn(night, '2026-11-21', 'Europe/Berlin')).toEqual({ start: 0, end: 180 })
    expect(segmentOn(night, '2026-11-22', 'UTC')).toBeNull()
  })

  test('on the day of the clock change a time keeps its place on the clock', () => {
    const ten = { start: '2027-03-28T08:00:00Z', end: '2027-03-28T09:00:00Z', all_day: false }
    expect(segmentOn(ten, '2027-03-28', 'Europe/Berlin')).toEqual({ start: 600, end: 660 })
  })
})
