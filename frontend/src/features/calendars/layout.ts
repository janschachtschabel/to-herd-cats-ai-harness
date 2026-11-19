import { isoToZoned } from '@/features/automations/zoned'
import { daysOf, type Day, type Timed } from './dates'

/** A span of one day in minutes of the wall clock (0 … 1440). */
export interface Span {
  start: number
  end: number
}

export interface Placed<T> {
  item: T
  /** The column, from 0, and how many columns its group of overlapping events has. */
  column: number
  columns: number
}

/** Side by side columns for a day's timed events: events that overlap, directly or
 *  through a chain, form a group that shares the width; each event takes the first
 *  column free when it starts (one that ends as another begins frees it). Earlier
 *  first; at the same start the longer first, then the given order. */
export function columns<T extends Span>(items: readonly T[]): Placed<T>[] {
  const order = items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => a.item.start - b.item.start || b.item.end - a.item.end || a.index - b.index)
  const placed: Placed<T>[] = []
  let group: Placed<T>[] = []
  let ends: number[] = [] // per column of the group: when it is free again
  let groupEnd = -Infinity
  const close = () => {
    for (const p of group) p.columns = ends.length
    group = []
    ends = []
  }
  for (const { item } of order) {
    if (item.start >= groupEnd) {
      close()
      groupEnd = -Infinity
    }
    let column = ends.findIndex((end) => end <= item.start)
    if (column === -1) column = ends.push(item.end) - 1
    else ends[column] = item.end
    const entry: Placed<T> = { item, column, columns: 0 }
    group.push(entry)
    placed.push(entry)
    groupEnd = Math.max(groupEnd, item.end)
  }
  close()
  return placed
}

const END_OF_DAY = 1440

function minutesOf(iso: string, zone: string): { day: Day; minutes: number } {
  const wall = isoToZoned(iso, zone)
  const [h, m] = wall.time.split(':').map(Number)
  return { day: wall.date, minutes: (h ?? 0) * 60 + (m ?? 0) }
}

/** Where a timed occurrence lies on `day` of the grid, in the viewer's wall minutes
 *  (a time keeps its place on the clock on the day of a clock change); cut at the
 *  day's bounds; null when it does not touch the day. */
export function segmentOn(occurrence: Timed, day: Day, zone: string): Span | null {
  const start = minutesOf(occurrence.start, zone)
  const end = minutesOf(occurrence.end, zone)
  if (start.day > day || end.day < day) return null
  if (end.day === day && end.minutes === 0 && start.day < day) return null
  const from = start.day < day ? 0 : start.minutes
  const to = end.day > day ? END_OF_DAY : end.minutes
  return { start: from, end: Math.max(to, from) }
}

/** Whether an occurrence belongs in the all-day row of the time grid: all-day ones,
 *  and timed ones of a day or more (shorter ones crossing midnight show on both days). */
export function inAllDayRow(occurrence: Timed): boolean {
  if (occurrence.all_day) return true
  return new Date(occurrence.end).getTime() - new Date(occurrence.start).getTime() >= 86_400_000
}

/** The occurrences of each day they touch for the viewer, in the order the views show
 *  them (all-day first, then by start). */
export function byDay<T extends Timed>(
  occurrences: readonly T[],
  zone: string,
  order: (a: T, b: T) => number,
): Map<Day, T[]> {
  const days = new Map<Day, T[]>()
  for (const occurrence of occurrences) {
    for (const day of daysOf(occurrence, zone)) {
      const list = days.get(day)
      if (list) list.push(occurrence)
      else days.set(day, [occurrence])
    }
  }
  for (const list of days.values()) list.sort(order)
  return days
}
