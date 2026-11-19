"""iCalendar (RFC 5545) for the calendar (plan M10 decision 10): pure functions, no
database, no routes. The only package that imports `icalendar`
(`tests/test_calendar_imports.py`).

- `reading.parse` is lenient: it takes what a file means, brings odd forms (an
  `UNTIL` as a date or a local time, an `EXDATE` as a date or in another zone) to the
  series' wall times, and counts by code (`problems`) whatever it leaves out; it never
  raises for the file's sake.
- `writing` is strict: it writes only the RFC's forms, with a `VTIMEZONE` for every zone
  it names; a redacted event carries its time and "busy" only.

`icalendar` reads lines (unfolding, parameters, escapes) and writes components
(folding, escapes, `VTIMEZONE`s from `zoneinfo`). Its own decoding of dates is not used:
it resolves zone names through a process-wide cache that every parsed `VTIMEZONE`
feeds, so one organisation's file would define zones for the next. Zones are resolved
here instead (`zones`), per file.
"""
