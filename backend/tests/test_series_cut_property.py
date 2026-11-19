"""A split without a change keeps every occurrence where it was (review M10 task 3b,
R3b-3 and R3b-4): seeded random series (clock changes in Berlin, New York and Sydney,
all-day, COUNT, UNTIL, endless, RDATEs at other times and in gaps, EXDATEs), each cut
at a random occurrence (RDATEs and gap occurrences included). The two parts together
have exactly the series' occurrences, by start, end and recurrence id; the new part
starts at an occurrence that can be a stored start and runs a rule that parses."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import Occurrence, Series, SeriesInvalid
from app.modules.calendars.recurrence_rule import WEEKDAYS, parse_rule
from app.modules.calendars.recurrence_series import instant
from app.modules.calendars.series_cut import cut, first_live, round_trips

SEED = 20261119
CASES = 600
ZONES = ("Europe/Berlin", "America/New_York", "Australia/Sydney", None)
# Days around the clock changes of 2026 and 2027 in the three zones.
CHANGES = (
    datetime(2026, 3, 8),
    datetime(2026, 3, 29),
    datetime(2026, 4, 5),
    datetime(2026, 10, 4),
    datetime(2026, 10, 25),
    datetime(2026, 11, 1),
    datetime(2027, 3, 14),
    datetime(2027, 3, 28),
    datetime(2027, 10, 31),
)


def _start(rng: random.Random, tzid: str | None) -> datetime:
    day = rng.choice(CHANGES) - timedelta(days=rng.randint(0, 20))
    if tzid is None:
        return day
    start = day.replace(hour=rng.choice((2, 2, 1, 9)), minute=rng.choice((0, 30)))
    probe = Series(start=start, duration=timedelta(hours=1), tzid=tzid, all_day=False)
    while not round_trips(probe, start):  # a stored start is an instant: no gap time
        start += timedelta(days=1)
        probe = Series(start=start, duration=timedelta(hours=1), tzid=tzid, all_day=False)
    return start


def _rule(rng: random.Random, start: datetime, tzid: str | None) -> str:
    freq = rng.choice(("DAILY", "WEEKLY", "WEEKLY", "MONTHLY", "YEARLY"))
    parts = [f"FREQ={freq}"]
    if rng.random() < 0.4:
        parts.append(f"INTERVAL={rng.randint(2, 3)}")
    if freq == "WEEKLY" and rng.random() < 0.5:
        days = sorted(rng.sample(range(7), rng.randint(1, 3)))
        parts.append("BYDAY=" + ",".join(WEEKDAYS[d] for d in days))
    if freq == "MONTHLY" and rng.random() < 0.4:
        parts.append(f"BYDAY={rng.choice((1, 2, -1))}{WEEKDAYS[rng.randrange(7)]}")
    if freq == "YEARLY" and rng.random() < 0.3:
        parts.append(f"BYMONTH={start.month},{(start.month + 5) % 12 + 1}")
    ending = rng.random()
    if ending < 0.45:
        parts.append(f"COUNT={rng.randint(3, 30)}")
    elif ending < 0.85:
        until = instant(_probe(start, tzid), start) + timedelta(days=rng.randint(20, 500))
        if tzid is None:
            parts.append(f"UNTIL={until:%Y%m%d}")
        else:
            parts.append(f"UNTIL={until.astimezone(UTC):%Y%m%dT%H%M%SZ}")
    return ";".join(parts)


def _probe(start: datetime, tzid: str | None) -> Series:
    return Series(start=start, duration=timedelta(days=1), tzid=tzid, all_day=tzid is None)


def _series(rng: random.Random) -> Series:
    tzid = rng.choice(ZONES)
    start = _start(rng, tzid)
    duration = timedelta(days=1) if tzid is None else timedelta(minutes=rng.choice((30, 60)))
    rdates = []
    for _ in range(rng.randint(0, 4)):
        day = start + timedelta(days=rng.randint(1, 300))
        if tzid is not None and rng.random() < 0.6:  # another time of day, gaps included
            day = day.replace(hour=rng.choice((2, 2, 3, 14)), minute=rng.choice((15, 45)))
        rdates.append(day)
    if tzid is not None and rng.random() < 0.5:  # an RDATE in a clock-change gap
        rdates.append(rng.choice(CHANGES).replace(hour=2, minute=15))
    rdates = [d for d in rdates if d > start]
    base = Series(
        start=start,
        duration=duration,
        tzid=tzid,
        all_day=tzid is None,
        rrule=_rule(rng, start, tzid),
        rdates=tuple(rdates),
    )
    walls = _walls(base)[:40]
    exdates = tuple(rng.sample(walls, max(0, min(len(walls) - 2, rng.randint(0, 3)))))
    return Series(**{**_fields(base), "exdates": exdates})


def _fields(series: Series) -> dict[str, object]:
    return {name: getattr(series, name) for name in Series.__slots__}


def _walls(series: Series) -> list[datetime]:
    return [o.recurrence_id for o in _all(series)]


def _all(series: Series, of: Series | None = None) -> list[Occurrence]:
    """The occurrences of `series` in the window of the series `of` (itself)."""
    first = of or series
    begin = instant(first, first.start) - timedelta(days=2)
    return recurrence.occurrences(series, begin, begin + timedelta(days=900), limit=5000)


def _key(occurrences: list[Occurrence]) -> list[tuple[datetime, datetime, datetime]]:
    return sorted((o.start, o.end, o.recurrence_id) for o in occurrences)


def test_a_split_without_a_change_keeps_every_occurrence() -> None:
    rng = random.Random(SEED)
    cases = gaps = rdates = strays = 0
    while cases < CASES:
        try:
            series = _series(rng)
        except SeriesInvalid:
            continue
        live = _walls(series)
        candidates = [w for w in live[:60] if w != first_live(series)]
        if not candidates:
            continue
        in_gaps = [w for w in candidates if not round_trips(series, w)]
        wall = rng.choice(in_gaps if in_gaps and rng.random() < 0.7 else candidates)
        cases += 1
        gaps += not round_trips(series, wall)
        rdates += wall in series.rdates
        parts = cut(series, wall)
        strays += bool(parts.strays)
        together = _all(parts.old, series) + (_all(parts.new, series) if parts.new else [])
        context = f"{series} split at {wall}: {parts}"
        assert _key(together) == _key(_all(series)), context
        if parts.new is not None:
            assert round_trips(parts.new, parts.new.start), context
            assert parts.new.start >= wall, context
            recurrence.check_series(parts.new)
            if parts.new.rrule:
                assert parse_rule(parts.new.rrule).text == parts.new.rrule, context
        assert all(w >= wall for w in parts.strays), context
    # The seed reaches what the test is about.
    assert gaps >= 10 and rdates >= 20 and strays >= 20, (gaps, rdates, strays)


@pytest.mark.parametrize(
    ("rule", "start", "expected"),
    [
        ("FREQ=WEEKLY;COUNT=4", datetime(2026, 11, 23, 9), "FREQ=WEEKLY;COUNT=4;BYDAY=MO"),
        ("FREQ=MONTHLY", datetime(2026, 1, 31, 9), "FREQ=MONTHLY;BYMONTHDAY=31"),
        ("FREQ=YEARLY", datetime(2028, 2, 29, 9), "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29"),
        ("FREQ=YEARLY;BYMONTH=3,9", datetime(2026, 3, 5), "FREQ=YEARLY;BYMONTH=3,9;BYMONTHDAY=5"),
        ("FREQ=WEEKLY;BYDAY=TU", datetime(2026, 11, 24, 9), "FREQ=WEEKLY;BYDAY=TU"),
        ("FREQ=DAILY;INTERVAL=2", datetime(2026, 11, 24, 9), "FREQ=DAILY;INTERVAL=2"),
    ],
)
def test_the_new_part_writes_out_what_its_rule_takes_from_dtstart(
    rule: str, start: datetime, expected: str
) -> None:
    from app.modules.calendars.series_cut import explicit_rule

    assert explicit_rule(parse_rule(rule), start).text == expected
