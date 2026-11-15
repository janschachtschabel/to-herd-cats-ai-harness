/** Wall times in an IANA zone without a date library: an automation's terms are in
 *  its own zone, the reader sees them in theirs (`formatTerm` names both). */

const DATE = /^(\d{4})-(\d{2})-(\d{2})$/
const TIME = /^([01]\d|2[0-3]):([0-5]\d)$/

/** The zone of this browser (the default for a new automation). */
export function viewerZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

/** Every zone this browser knows, for the zone picker (the API checks its own list). */
export function timeZones(): string[] {
  const own = viewerZone()
  const known =
    typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
  return known.includes(own) ? known : [own, ...known]
}

export function isZone(zone: string): boolean {
  try {
    new Intl.DateTimeFormat('en', { timeZone: zone })
    return true
  } catch {
    return false
  }
}

const partsFormat = (zone: string) =>
  new Intl.DateTimeFormat('en-US', {
    timeZone: zone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

/** The wall clock of `instant` in `zone`, as if it were UTC (ms). */
function wallClock(instant: number, zone: string): number {
  const parts = Object.fromEntries(
    partsFormat(zone)
      .formatToParts(new Date(instant))
      .map((p) => [p.type, p.value]),
  )
  return Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  )
}

/** The instant of a wall time in a zone (ISO, UTC); a time the clock change skips
 *  becomes the next valid one, as the API does with terms. Null while incomplete. */
export function zonedToIso(date: string, time: string, zone: string): string | null {
  const d = DATE.exec(date)
  const t = TIME.exec(time)
  if (!d || !t || !isZone(zone)) return null
  const wanted = Date.UTC(Number(d[1]), Number(d[2]) - 1, Number(d[3]), Number(t[1]), Number(t[2]))
  let guess = wanted - (wallClock(wanted, zone) - wanted)
  // A second pass settles a guess that crossed the zone's offset change (a skipped
  // wall time lands as far past the gap as it was into it).
  guess = wanted - (wallClock(guess, zone) - guess)
  return new Date(guess).toISOString()
}

/** The wall time of an instant in a zone, for the date and time fields. */
export function isoToZoned(iso: string, zone: string): { date: string; time: string } {
  const wall = new Date(wallClock(new Date(iso).getTime(), zone)).toISOString()
  return { date: wall.slice(0, 10), time: wall.slice(11, 16) }
}

/** A term in the reader's time (`local`) and, where the automation's zone differs
 *  from the reader's, the time it is there (`there`, shown with the zone's name). */
export function formatTerm(
  iso: string,
  locale: string,
  readerZone: string,
  zone: string | null,
): { local: string; there: string | null } {
  const at = new Date(iso)
  const local = new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: readerZone,
  }).format(at)
  if (!zone || zone === readerZone || !isZone(zone)) return { local, there: null }
  const there = new Intl.DateTimeFormat(locale, { timeStyle: 'short', timeZone: zone }).format(at)
  return { local, there }
}
