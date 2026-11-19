"""Re-check of the fix wave for M10 Task 7a (`recheck-task-7a.md`, RC7a-1 to RC7a-5):
five small files whose reading still costs far more than their bytes, each through a
path the work budget (`ical.budget`) does not count. Work is counted (Python calls as
`test_ical_hostile` counts them, characters looked up, elements walked), never timed."""

import sys
from datetime import datetime, timedelta
from types import FrameType

import pytest

from app.modules.calendars import recurrence_ids
from app.modules.calendars import zones as calendar_zones
from app.modules.calendars.ical import reading
from app.modules.calendars.ical import zones as ical_zones
from app.modules.calendars.recurrence import Series

_HEAD = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
_TAIL = "END:VCALENDAR\r\n"
_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


class _TooManyCalls(BaseException):
    """Stops a reading that went past its bound (no guard of `parse` catches it)."""


def _calls(data: bytes, bound: int) -> int:
    """The Python calls `reading.parse` makes for `data`; stopped at `bound + 1`."""
    count = 0

    def note(frame: FrameType, event: str, arg: object) -> None:
        nonlocal count
        if event == "call":
            count += 1
            if count > bound:
                raise _TooManyCalls

    sys.setprofile(note)
    try:
        reading.parse(data, default_zone="Europe/Berlin", limit=5000)
    except _TooManyCalls:
        pass
    finally:
        sys.setprofile(None)
    return count


def _event(uid: str, body: str) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%S")


def _calendar(*parts: str) -> bytes:
    return (_HEAD + "".join(parts) + _TAIL).encode()


def test_a_vtimezone_of_long_rules_costs_no_more_than_the_budget_counts() -> None:
    """RC7a-1: a VTIMEZONE's yearly rule may list every month and 77 weekdays (388
    characters, a rule `parse_rule` takes). One `offset_at` then builds 1,848 months'
    day lists per ruled observance and is charged 12 units; the 3,000 look-ups for one
    event (its times, three years, the reference years) run 437 s for this 10 KiB file
    (measured), and the whole budget buys about 20 minutes."""
    days = [
        *_DAYS,
        *(f"{sign}{n}{day}" for n in range(1, 6) for sign in ("", "-") for day in _DAYS),
    ]
    rule = "FREQ=YEARLY;BYMONTH=1,2,3,4,5,6,7,8,9,10,11,12;BYDAY=" + ",".join(days)
    assert len(rule) <= 500
    observance = (
        "BEGIN:STANDARD\r\nDTSTART:16010101T000000\r\nTZOFFSETFROM:+0000\r\n"
        f"TZOFFSETTO:+0000\r\nRRULE:{rule}\r\nEND:STANDARD\r\n"
    )
    zone = "BEGIN:VTIMEZONE\r\nTZID:Z\r\n" + observance * 20 + "END:VTIMEZONE\r\n"
    data = _calendar(zone, _event("u", "DTSTART;TZID=Z:20260101T100000"))
    assert len(data) < 11_000
    # Europe's rules under an unknown name cost about 180,000 calls for one event.
    assert _calls(data, 1_000_000) <= 1_000_000


def test_a_sparse_counted_rule_is_not_scanned_for_each_exdate_uncounted() -> None:
    """RC7a-2: a counted rule is expanded from its start to the latest value asked
    for, and the budget is told one unit per wall time *found*. A daily rule that
    matches every 28 years (29 February on a Monday) is scanned day by day over 500
    years for one EXDATE in 2399 and finds 18: 640,000 calls and 0.35 s per event of
    150 bytes, 20 units charged. 5,000 such events (750 KiB) take half an hour."""
    body = (
        "DTSTART:19040229T100000Z\r\n"
        "RRULE:FREQ=DAILY;BYMONTH=2;BYMONTHDAY=29;BYDAY=MO;COUNT=5000\r\n"
        "EXDATE:23990101T100000Z"
    )
    data = _calendar(*(_event(f"e{n}", body) for n in range(20)))
    assert len(data) < 4_000
    assert _calls(data, 1_000_000) <= 1_000_000


def test_a_vtimezone_of_many_observances_costs_no_more_than_the_budget_counts() -> None:
    """RC7a-5: `offset_cost` counts ruled observances only, but `offset_at` walks every
    observance (up to `MAX_OBSERVANCES` = 1,000) at each wall time: about 2,400 calls
    for one unit. 5 MiB of such events cost 390 million calls and 40 s (measured),
    against the 15 million `test_ical_hostile` allows."""
    observance = (
        "BEGIN:STANDARD\r\nDTSTART:23990101T000000\r\nTZOFFSETFROM:+0000\r\n"
        "TZOFFSETTO:+0000\r\nEND:STANDARD\r\n"
    )
    zone = "BEGIN:VTIMEZONE\r\nTZID:Z\r\n" + observance * 1000 + "END:VTIMEZONE\r\n"
    first = datetime(2026, 1, 1, 10)
    exdates = ",".join(_stamp(first + timedelta(days=n)) for n in range(1, 32))
    body = f"DTSTART;TZID=Z:{_stamp(first)}\r\nRRULE:FREQ=DAILY\r\nEXDATE;TZID=Z:{exdates}"
    data = _calendar(zone, *(_event(f"e{n}", body) for n in range(60)))
    assert len(data) < 140_000
    # 15,000,000 calls for 5 MiB are 400,000 for this file; allow four times that.
    assert _calls(data, 1_600_000) <= 1_600_000


class _Looked:
    """`zones.names()`, counting the characters of every name looked up in it."""

    def __init__(self, names: frozenset[str]) -> None:
        self.names = names
        self.characters = 0

    def __contains__(self, name: object) -> bool:
        if isinstance(name, str):
            self.characters += len(name)
        return name in self.names


def test_a_tzid_of_slashes_is_not_looked_up_once_per_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RC7a-3: `by_name` tries every suffix of a TZID that begins with a slash, each
    joined anew: quadratic in the TZID, inside `str.join`, where neither the budget nor
    a count of Python calls sees it. One TZID of 78 KiB takes 4 s, of 313 KiB 110 s
    (measured), of 5 MiB hours; no VTIMEZONE is needed."""
    looked = _Looked(calendar_zones.names())
    monkeypatch.setattr(calendar_zones, "names", lambda: looked)
    tzid = "/" + "a/" * 2000
    assert ical_zones.by_name(tzid) is None
    assert looked.characters <= 10 * len(tzid), looked.characters


class _Walked(tuple[datetime, ...]):
    """A series' RDATEs, counting how often they are walked."""

    walks = 0

    def __iter__(self):  # type: ignore[no-untyped-def]
        type(self).walks += 1
        return super().__iter__()


def test_the_rdates_of_a_series_are_not_walked_for_every_cluster_of_values_uncounted() -> None:
    """RC7a-4: every pass over a cluster of values (`recurrence.walls`) builds a set of
    all the series' RDATEs and filters it, and the budget hears of the wall times found
    only. 80,000 RDATEs and 40,000 EXDATEs 40 days apart (1.25 MiB, one event) take
    152 s (measured); 5 MiB about 40 minutes."""
    first = datetime(1900, 1, 1, 10)
    rdates = _Walked(first + timedelta(seconds=n) for n in range(1, 5001))
    series = Series(first, timedelta(hours=1), "UTC", False, rrule="FREQ=YEARLY", rdates=rdates)
    values = [datetime(1901, 3, 1, 10) + timedelta(days=40 * n) for n in range(400)]
    spent = 0

    def spend(units: int) -> None:
        nonlocal spent
        spent += units

    _Walked.walks = 0
    recurrence_ids.named(series, values, spend)
    walked = _Walked.walks * len(rdates)  # elements looked at
    # a unit is about a microsecond: it pays for some tens of elements, not thousands
    assert walked <= 50 * spent, (walked, spent)
