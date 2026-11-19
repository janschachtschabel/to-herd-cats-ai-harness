"""Hostile iCalendar files of a given size from the re-check of M10 Task 7a (RC7a-1 to
RC7a-5), and the most expensive input each price of `ical.budget` and each structural
cap still accepts. `test_ical_hostile` reads them with the shapes of `ical_hostile`."""

from collections.abc import Callable
from datetime import datetime, timedelta

from app.modules.calendars.ical import vtimezone, zones
from tests.support.ical_hostile import _HEAD, _TAIL, _event, _repeat, _stamp

_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def _zone(tzid: str, observances: str) -> str:
    return f"BEGIN:VTIMEZONE\r\nTZID:{tzid}\r\n{observances}END:VTIMEZONE\r\n"


def _observance(rule: str, start: str = "16010101T000000", rdates: str = "") -> str:
    lines = f"RRULE:{rule}\r\n" if rule else ""
    lines += f"RDATE:{rdates}\r\n" if rdates else ""
    return (
        f"BEGIN:STANDARD\r\nDTSTART:{start}\r\nTZOFFSETFROM:+0000\r\nTZOFFSETTO:+0000\r\n"
        f"{lines}END:STANDARD\r\n"
    )


def _daily_events(tzid: str, first: datetime) -> Callable[[int], str]:
    return lambda n: _event(f"e{n}", f"DTSTART;TZID={tzid}:{_stamp(first + timedelta(days=n))}")


def a_vtimezone_of_long_rules(size: int) -> bytes:
    """RC7a-1: every month and 77 weekdays in each of 20 rules, used by every event:
    refused by the rule's list caps."""
    days = [*_DAYS, *(f"{s}{n}{d}" for n in range(1, 6) for s in ("", "-") for d in _DAYS)]
    rule = "FREQ=YEARLY;BYMONTH=1,2,3,4,5,6,7,8,9,10,11,12;BYDAY=" + ",".join(days)
    head = _HEAD + _zone("Z", _observance(rule) * vtimezone.MAX_RULED)
    return _repeat(size, head, _daily_events("Z", datetime(2026, 1, 1, 10)))


def a_vtimezone_at_its_rule_caps(size: int) -> bytes:
    """RC7a-1's price: as many ruled observances as are compared, each with the most
    months, weekdays and days of the month a rule may list, used by every event on a
    day of its own."""
    months = ",".join(str(m) for m in range(1, vtimezone.MAX_RULE_MONTHS + 1))
    days = ",".join(f"{n}{d}" for n, d in zip((1, 2, -1), _DAYS, strict=False))
    monthdays = ",".join(str(d) for d in range(1, vtimezone.MAX_RULE_MONTHDAYS + 1))
    assert len(days.split(",")) == vtimezone.MAX_RULE_DAYS
    rule = f"FREQ=YEARLY;BYMONTH={months};BYDAY={days};BYMONTHDAY={monthdays}"
    head = _HEAD + _zone("Z", _observance(rule) * vtimezone.MAX_RULED)
    return _repeat(size, head, _daily_events("Z", datetime(1950, 1, 1, 10)))


def _sparse(exdate: str) -> Callable[[int], str]:
    body = (
        "DTSTART:19040229T100000Z\r\n"
        "RRULE:FREQ=DAILY;BYMONTH=2;BYMONTHDAY=29;BYDAY=MO;COUNT=5000\r\n"
        f"EXDATE:{exdate}"
    )
    return lambda n: _event(f"e{n}", body)


def sparse_counted_rules_with_a_far_exdate(size: int) -> bytes:
    """RC7a-2: a counted rule that matches every 28 years, one EXDATE in 2399 it cannot
    name."""
    return _repeat(size, _HEAD, _sparse("23990101T100000Z"))


def sparse_counted_rules_with_a_far_occurrence(size: int) -> bytes:
    """RC7a-2's price: the same rule, its EXDATE on its last occurrence (2388): counted
    from the start, day by day over 484 years, for every event."""
    return _repeat(size, _HEAD, _sparse("23880229T100000Z"))


def a_vtimezone_of_many_observances(size: int) -> bytes:
    """RC7a-5: as many observances without a rule as a definition may have, every event
    with 31 EXDATEs in it."""
    first = datetime(2026, 1, 1, 10)
    head = _HEAD + _zone("Z", _observance("", "23990101T000000") * vtimezone.MAX_OBSERVANCES)
    exdates = ",".join(_stamp(first + timedelta(days=n)) for n in range(1, 32))
    body = f"DTSTART;TZID=Z:{_stamp(first)}\r\nRRULE:FREQ=DAILY\r\nEXDATE;TZID=Z:{exdates}"
    return _repeat(size, head, lambda n: _event(f"e{n}", body))


def vtimezones_at_their_onset_cap(size: int) -> bytes:
    """The price of building a definition: VTIMEZONEs of as many onsets as one may have,
    each used by one event."""
    rdates = ",".join(
        _stamp(datetime(1700, 1, 1) + timedelta(days=n)) for n in range(vtimezone.MAX_ONSETS - 1)
    )
    observance = _observance("", rdates=rdates)
    return _repeat(
        size,
        _HEAD,
        lambda n: (
            _zone(f"Z{n}", observance) + _event(f"e{n}", f"DTSTART;TZID=Z{n}:20260101T100000")
        ),
    )


def a_tzid_of_slashes(size: int) -> bytes:
    """RC7a-3: one TZID of slashes as long as the file, no VTIMEZONE."""
    tzid = "/a" * (size // 2)
    return (_HEAD + _event("u", f"DTSTART;TZID={tzid}:20260101T100000") + _TAIL).encode()


def tzids_at_their_caps(size: int) -> bytes:
    """RC7a-3's price: every event in a TZID as long and of as many parts as is looked
    up, which names no zone."""
    parts = zones.MAX_TZID_SEGMENTS
    tzid = "/" + "/".join(["x" * ((zones.MAX_TZID - parts) // parts)] * parts)
    assert len(tzid) <= zones.MAX_TZID and not zones.too_large(tzid)
    return _repeat(size, _HEAD, lambda n: _event(f"e{n}", f"DTSTART;TZID={tzid}:20260101T100000"))


def rdates_beside_exdate_clusters(size: int) -> bytes:
    """RC7a-4: one endless series, RDATEs and EXDATEs 40 days apart, each EXDATE a
    cluster of its own (the RDATEs beyond `MAX_RDATES` are counted)."""
    first = datetime(1900, 1, 1, 10)

    def spread(count: int, hours: int) -> str:
        # 40 days apart over 438 years, a minute later in each round
        return ",".join(
            _stamp(first + timedelta(days=40 * (n % 4000), hours=hours, minutes=n // 4000))
            for n in range(1, count)
        )

    rdates, exdates = spread(size // 128, 1), spread(size // 17, 0)
    body = (
        f"DTSTART;TZID=Europe/Berlin:{_stamp(first)}\r\nRRULE:FREQ=YEARLY\r\n"
        f"RDATE;TZID=Europe/Berlin:{rdates}\r\nEXDATE;TZID=Europe/Berlin:{exdates}"
    )
    return (_HEAD + _event("u", body) + _TAIL).encode()


SHAPES: dict[str, Callable[[int], bytes]] = {
    shape.__name__: shape
    for shape in (
        a_vtimezone_of_long_rules,
        a_vtimezone_at_its_rule_caps,
        sparse_counted_rules_with_a_far_exdate,
        sparse_counted_rules_with_a_far_occurrence,
        a_vtimezone_of_many_observances,
        vtimezones_at_their_onset_cap,
        a_tzid_of_slashes,
        tzids_at_their_caps,
        rdates_beside_exdate_clusters,
    )
}
