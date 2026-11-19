"""Hostile iCalendar files of a given size (review M10 Task 7a): each shape aims at one
place where reading once did more work than its bytes, or raised. `SIZE` is the import
limit (plan M10 decision 10: `HERD_CALENDAR_IMPORT_MAX_BYTES`, 5 MiB)."""

from collections.abc import Callable
from datetime import datetime, timedelta

from app.modules.calendars.ical.vtimezone import MAX_RULED

SIZE = 5 * 1024 * 1024

# Europe's rules under a name no table knows (Outlook's "Customized Time Zone").
_CUSTOM = (
    "BEGIN:VTIMEZONE\r\nTZID:{tzid}\r\n"
    "BEGIN:STANDARD\r\nDTSTART:16011028T030000\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\n"
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU{extra}\r\nEND:STANDARD\r\n"
    "BEGIN:DAYLIGHT\r\nDTSTART:16010325T020000\r\nTZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\n"
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\nEND:DAYLIGHT\r\n"
    "END:VTIMEZONE\r\n"
)
_HEAD = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
_TAIL = "END:VCALENDAR\r\n"


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%S")


def _event(uid: str, body: str) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


def _repeat(size: int, head: str, unit: Callable[[int], str], tail: str = _TAIL) -> bytes:
    parts = [head]
    used = len(head) + len(tail)
    number = 0
    while used < size:
        piece = unit(number)
        parts.append(piece)
        used += len(piece)
        number += 1
    return ("".join(parts) + tail).encode()


def _values(
    size: int, first: datetime, step: timedelta, form: str = "", period: int = 10**9
) -> str:
    count = size // (16 + len(form))
    return ",".join(_stamp(first + step * (n % period)) + form for n in range(1, count))


def exdates_in_a_files_own_zone(size: int) -> bytes:
    """R7a-1: one event, every EXDATE in a TZID only the file defines."""
    first = datetime(2026, 6, 1, 10)
    body = (
        f"DTSTART;TZID=Custom:{_stamp(first)}\r\nRRULE:FREQ=DAILY\r\n"
        f"EXDATE;TZID=Custom:{_values(size, first, timedelta(minutes=1))}"
    )
    return (_HEAD + _CUSTOM.format(tzid="Custom", extra="") + _event("u", body) + _TAIL).encode()


def stray_ends(size: int) -> bytes:
    """R7a-2: components opened, then ENDs of another name."""
    count = size // 14
    return (_HEAD + "BEGIN:A\r\n" * count + "END:B\r\n" * count).encode()


def nested_alarms(size: int) -> bytes:
    """R7a-3: alarms nested inside alarms inside one event."""
    count = size // 28
    return (
        _HEAD
        + "BEGIN:VEVENT\r\nUID:u\r\nDTSTART:20260101T100000Z\r\n"
        + "BEGIN:VALARM\r\n" * count
        + "END:VALARM\r\n" * count
        + "END:VEVENT\r\n"
        + _TAIL
    ).encode()


def durations_beyond_datetime(size: int) -> bytes:
    """R7a-3: durations that leave `datetime`'s years."""
    return _repeat(
        size, _HEAD, lambda n: _event(f"e{n}", "DTSTART:20260101T100000\r\nDURATION:P999999W")
    )


def vtimezone_rules_beyond_datetime(size: int) -> bytes:
    """R7a-3: a VTIMEZONE whose counted rule ends after the year 9999, used by every
    event."""
    head = _HEAD + _CUSTOM.format(tzid="Custom", extra=";COUNT=5000;INTERVAL=3")
    return _repeat(
        size,
        head,
        lambda n: _event(
            f"e{n}",
            f"DTSTART;TZID=Custom:{_stamp(datetime(1990, 1, 1, 10) + timedelta(days=n))}",
        ),
    )


def overrides_at_the_end_of_a_counted_series(size: int) -> bytes:
    """R7a-4: one counted series, every override names its last occurrence."""
    first = datetime(2026, 1, 1, 10)
    last = _stamp(first + timedelta(days=4999))
    series = _event("s", f"DTSTART:{_stamp(first)}Z\r\nRRULE:FREQ=DAILY;COUNT=5000")
    override = _event("s", f"DTSTART:{last}Z\r\nRECURRENCE-ID:{last}Z\r\nSUMMARY:again")
    return _repeat(size, _HEAD + series, lambda n: override)


def rules_that_never_match(size: int) -> bytes:
    """Every event's rule is scanned to the horizon before it is found dead: every
    seventh day from a Monday is never a Tuesday."""
    rule = "DTSTART:19000101T100000Z\r\nRRULE:FREQ=DAILY;INTERVAL=7;BYDAY=TU"
    return _repeat(size, _HEAD, lambda n: _event(f"e{n}", rule))


def a_zone_per_event(size: int) -> bytes:
    """Every event in a TZID of its own that only the file defines."""
    return _repeat(
        size,
        _HEAD,
        lambda n: (
            _CUSTOM.format(tzid=f"Z{n}", extra="")
            + _event(f"e{n}", f"DTSTART;TZID=Z{n}:20260710T090000")
        ),
    )


def utc_exdates_beside_a_counted_series(size: int) -> bytes:
    """R7a-6's path: EXDATEs as instants that name no occurrence, so each is looked
    for as an occurrence in a gap."""
    first = datetime(2026, 1, 1, 10)
    body = (
        f"DTSTART;TZID=Europe/Berlin:{_stamp(first)}\r\nRRULE:FREQ=DAILY;COUNT=5000\r\n"
        f"EXDATE:{_values(size, first + timedelta(minutes=7), timedelta(hours=5), 'Z')}"
    )
    return (_HEAD + _event("u", body) + _TAIL).encode()


def utc_exdates_spread_over_an_endless_series(size: int) -> bytes:
    """The same, far apart on an endless daily series: one pass per cluster."""
    first = datetime(1900, 1, 1, 10)
    body = (
        f"DTSTART;TZID=Europe/Berlin:{_stamp(first)}\r\nRRULE:FREQ=DAILY\r\n"
        f"EXDATE:{_values(size, first + timedelta(minutes=7), timedelta(days=40, hours=5), 'Z', 4000)}"
    )
    return (_HEAD + _event("u", body) + _TAIL).encode()


def a_vtimezone_of_many_rules(size: int) -> bytes:
    """A definition of as many ruled observances as is compared, used by every event."""
    observance = (
        "BEGIN:STANDARD\r\nDTSTART:16011028T030000\r\nTZOFFSETFROM:+0200\r\n"
        "TZOFFSETTO:+0100\r\nRRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\r\nEND:STANDARD\r\n"
    )
    head = _HEAD + "BEGIN:VTIMEZONE\r\nTZID:Many\r\n" + observance * MAX_RULED + "END:VTIMEZONE\r\n"
    return _repeat(
        size,
        head,
        lambda n: _event(
            f"e{n}",
            f"DTSTART;TZID=Many:{_stamp(datetime(1950, 1, 1, 10) + timedelta(days=n))}\r\n"
            f"DTEND;TZID=Many:{_stamp(datetime(1950, 1, 1, 11) + timedelta(days=n))}",
        ),
    )


def plain_events(size: int) -> bytes:
    """No trick: what reading the bytes alone costs."""
    return _repeat(
        size,
        _HEAD,
        lambda n: _event(
            f"e{n}",
            "DTSTART;TZID=Europe/Berlin:20260105T100000\r\nDURATION:PT1H\r\n"
            "RRULE:FREQ=WEEKLY;BYDAY=MO\r\nSUMMARY:Standup",
        ),
    )


SHAPES: dict[str, Callable[[int], bytes]] = {
    shape.__name__: shape
    for shape in (
        exdates_in_a_files_own_zone,
        stray_ends,
        nested_alarms,
        durations_beyond_datetime,
        vtimezone_rules_beyond_datetime,
        overrides_at_the_end_of_a_counted_series,
        rules_that_never_match,
        a_zone_per_event,
        utc_exdates_beside_a_counted_series,
        utc_exdates_spread_over_an_endless_series,
        a_vtimezone_of_many_rules,
        plain_events,
    )
}
