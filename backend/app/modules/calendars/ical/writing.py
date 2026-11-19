"""Writing iCalendar (plan M10 decision 10: "Schreiben streng"): only the RFC's forms.

- A start with a zone is `DTSTART;TZID=<IANA>:<wall time>` with a VTIMEZONE for that
  zone (written once, before the first event that names it; from `zoneinfo`); one in
  UTC is written as an instant (`…Z`); all-day as `VALUE=DATE`.
- The end is `DTEND` in the start's form, or `DURATION` (hours, minutes, seconds:
  exact) where the end's wall time would not read back as the same instant (the second
  of a doubled hour).
- RRULE is the canonical text (`UNTIL` in UTC for a start with a zone, a date for an
  all-day one); RDATE, EXDATE and every RECURRENCE-ID are in the start's form.
- TRANSP is always written (all-day events are free by default here, not in RFC 5545).
- A redacted event (decision 3) carries its time, status, TRANSP and `CLASS:PRIVATE`
  only, under an opaque UID derived from its own (stable, so a feed stays a feed).
"""

import hashlib
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache

from icalendar import Alarm, Calendar, Event, Timezone, vCalAddress, vDuration, vText
from icalendar.prop import vInline

from app.modules.calendars import recurrence, zones
from app.modules.calendars.ical import lines
from app.modules.calendars.ical.drafts import (
    AttendeeDraft,
    Content,
    ExportEvent,
    Response,
    Role,
    Visibility,
)
from app.modules.calendars.recurrence import Series

PRODID = "-//to-herd-cats-ai//calendar//EN"
_UTC = "UTC"  # written as instants (`…Z`), the zone a series in UTC is read back in
_VTIMEZONE_YEARS = (1970, 2038)  # widened to an event's year where it lies outside
_PARTSTAT = {
    Response.NEEDS_ACTION: "NEEDS-ACTION",
    Response.ACCEPTED: "ACCEPTED",
    Response.TENTATIVE: "TENTATIVE",
    Response.DECLINED: "DECLINED",
}
_END = b"END:VCALENDAR\r\n"


def calendar_ics(events: Iterable[ExportEvent], *, name: str) -> Iterator[bytes]:
    """A calendar named `name`, one chunk per event (with the VTIMEZONEs it needs
    first)."""
    yield from _stream(events, name)


def event_ics(event: ExportEvent) -> bytes:
    return b"".join(_stream([event], None))


def _stream(events: Iterable[ExportEvent], name: str | None) -> Iterator[bytes]:
    head = Calendar()
    head.add("VERSION", "2.0")
    head.add("PRODID", PRODID)
    head.add("CALSCALE", "GREGORIAN")
    if name is not None:
        head.add("NAME", vText(_text(name)))
        head.add("X-WR-CALNAME", vText(_text(name)))
    yield head.to_ical().removesuffix(_END)
    written: set[str] = set()
    for event in events:
        chunk = b""
        for series in (event.series, *(o.series for o in event.overrides)):
            if series.tzid is not None and series.tzid != _UTC and series.tzid not in written:
                written.add(series.tzid)
                chunk += _vtimezone(series.tzid, *_years(series.start.year))
        yield chunk + b"".join(part.to_ical() for part in _vevents(event))
    yield _END


def _years(year: int) -> tuple[int, int]:
    first, last = _VTIMEZONE_YEARS
    return min(first, year), max(last, year + 1)


@lru_cache(maxsize=128)
def _vtimezone(tzid: str, first: int, last: int) -> bytes:
    found = Timezone.from_tzinfo(
        zones.zone(tzid), tzid=tzid, first_date=date(first, 1, 1), last_date=date(last, 1, 1)
    )
    return bytes(found.to_ical())


def _vevents(event: ExportEvent) -> Iterator[Event]:
    uid = _opaque(event.uid) if event.redacted else event.uid
    master = _vevent(uid, event.stamp, event.series, event.content, event.redacted)
    if not event.redacted:
        organiser = lines.valid_address(event.organiser or "")
        if organiser is not None:
            master.add("ORGANIZER", vCalAddress(f"mailto:{organiser}"))
        for minutes in event.alarms:
            master.add_component(_alarm(minutes, event.content.title))
    yield master
    for override in event.overrides:
        part = _vevent(uid, event.stamp, override.series, override.content, event.redacted)
        part.add(*_moment("RECURRENCE-ID", event.series, override.recurrence_id))
        yield part


def _vevent(uid: str, stamp: datetime, series: Series, content: Content, redacted: bool) -> Event:
    part = Event()
    part.add("UID", _text(uid))
    part.add("DTSTAMP", stamp.astimezone(UTC))
    part.add(*_moment("DTSTART", series, series.start))
    _end(part, series)
    if series.rrule:
        part.add("RRULE", vInline(recurrence.check_rule(series.rrule)))
    if series.rdates:
        part.add(*_moments("RDATE", series, series.rdates))
    if series.exdates:
        part.add(*_moments("EXDATE", series, series.exdates))
    part.add("STATUS", content.status.value.upper())
    part.add("TRANSP", "OPAQUE" if content.busy else "TRANSPARENT")
    if redacted or content.visibility is Visibility.PRIVATE:
        part.add("CLASS", "PRIVATE")
    if redacted:
        return part
    part.add("SEQUENCE", content.sequence)
    for key, text in (
        ("SUMMARY", content.title),
        ("LOCATION", content.location),
        ("DESCRIPTION", content.description),
    ):
        if text:
            part.add(key, _text(text))
    for attendee in content.attendees:
        if (written := _attendee(attendee)) is not None:
            part.add("ATTENDEE", written)
    return part


def _moment(key: str, series: Series, wall: datetime) -> tuple[str, object, dict[str, str]]:
    if series.all_day:
        return key, wall.date(), {}
    if series.tzid == _UTC:
        return key, wall.replace(tzinfo=UTC), {}
    return key, wall, {"TZID": series.tzid or ""}


def _moments(
    key: str, series: Series, walls: tuple[datetime, ...]
) -> tuple[str, object, dict[str, str]]:
    values = [_moment(key, series, wall)[1] for wall in walls]
    return key, values, _moment(key, series, series.start)[2]


def _end(part: Event, series: Series) -> None:
    if series.all_day:
        part.add("DTEND", (series.start + series.duration).date())
        return
    tzid = series.tzid or "UTC"
    begin = zones.localise(series.start, tzid)
    end = begin + series.duration
    wall = zones.wall(end, tzid)
    if zones.localise(wall, tzid) == end:
        part.add(*_moment("DTEND", series, wall))
    else:
        part.add("DURATION", vInline(_exact(series.duration)))


def _exact(duration: timedelta) -> str:
    """A duration in hours, minutes and seconds: never nominal days."""
    seconds = int(duration.total_seconds())
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    text = "".join(f"{n}{unit}" for n, unit in ((hours, "H"), (minutes, "M"), (seconds, "S")) if n)
    return f"PT{text or '0S'}"


def _alarm(minutes: int, title: str) -> Alarm:
    alarm = Alarm()
    alarm.add("ACTION", "DISPLAY")
    alarm.add("DESCRIPTION", _text(title) or "Reminder")
    alarm.add("TRIGGER", vDuration(-timedelta(minutes=minutes)))
    return alarm


def _attendee(attendee: AttendeeDraft) -> vCalAddress | None:
    email = lines.valid_address(attendee.email)
    if email is None:
        return None  # nothing that is no address goes out
    address = vCalAddress(f"mailto:{email}")
    if name := lines.one_line(attendee.name or ""):
        address.params["CN"] = name
    optional = attendee.role is Role.OPTIONAL
    address.params["ROLE"] = "OPT-PARTICIPANT" if optional else "REQ-PARTICIPANT"
    address.params["PARTSTAT"] = _PARTSTAT[attendee.response]
    return address


def _text(text: str) -> str:
    """A text as TEXT can carry it: line breaks as `\\n` (escaped by `vText`), no
    other control character, never a bare carriage return."""
    return lines.clean(text.replace("\r\n", "\n").replace("\r", "\n"))


def _opaque(uid: str) -> str:
    return f"{hashlib.sha256(uid.encode()).hexdigest()[:32]}@busy.invalid"
