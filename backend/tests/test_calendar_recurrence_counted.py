"""Counted series jump ahead (plan M10 Task 3c, remedy b): a rule with `COUNT` whose
every active period holds the same number of matches starts a far window whole blocks
later and counts what it skipped (DTSTART, the matches of the first block, n per block
after it), instead of walking from DTSTART on every read. Where the number per period
varies (the 31st, every Monday of a month, the 20th Monday of a year, a weekly
BYSETPOS, a day of a month a month may lack), it keeps walking.

Seeded and compared with the plain expansion by `dateutil` from DTSTART (COUNT applied
to DTSTART and the matches after it, RFC 5545 3.8.5.3), across DST changes, with
BYSETPOS, BYDAY with ordinals, EXDATEs, RDATEs and overrides."""

import random
import uuid
from datetime import UTC, datetime, timedelta
from itertools import islice

import pytest
from dateutil.rrule import rrulestr

from app.core.principal import PrincipalType
from app.modules.calendars import expansion, recurrence, recurrence_jump, zones
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.expansion import Budget
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_jump import Counter, week_start
from app.modules.calendars.recurrence_rule import parse_rule

SEED = 20261119
SERIES = 400
ZONES = ("Europe/Berlin", "America/New_York", "Australia/Sydney", "Pacific/Apia", "UTC", None)
# Rules whose count per period is fixed (they jump) and rules where it varies (they walk).
FIXED = (
    "FREQ=DAILY",
    "FREQ=DAILY;INTERVAL=3",
    "FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR",
    "FREQ=DAILY;INTERVAL=2;BYDAY=MO,WE,FR",
    "FREQ=WEEKLY",
    "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH;WKST=SU",
    "FREQ=WEEKLY;BYDAY=MO,SA,SU",
    "FREQ=MONTHLY;BYMONTHDAY=1,15,-1",
    "FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=28",
    "FREQ=MONTHLY;BYDAY=1MO",
    "FREQ=MONTHLY;BYDAY=2WE,-1FR",
    "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1",
    "FREQ=MONTHLY;BYDAY=TU,TH;BYSETPOS=1,2,-1",
    "FREQ=YEARLY",
    "FREQ=YEARLY;BYMONTH=11;BYDAY=4TH",
    "FREQ=YEARLY;BYMONTH=2,8;BYMONTHDAY=27,-1",
    "FREQ=YEARLY;INTERVAL=2;BYMONTHDAY=10",
)
WALKING = (
    "FREQ=MONTHLY;BYMONTHDAY=31",
    "FREQ=MONTHLY;BYMONTHDAY=1,-28",
    "FREQ=MONTHLY;BYDAY=MO",
    "FREQ=MONTHLY;BYDAY=1MO,-4MO",
    "FREQ=MONTHLY;BYDAY=5FR",
    "FREQ=MONTHLY;BYMONTH=1,7;BYMONTHDAY=3",
    "FREQ=MONTHLY;BYDAY=MO,TU;BYSETPOS=9",
    "FREQ=WEEKLY;BYDAY=MO,TU;BYSETPOS=1",
    "FREQ=DAILY;BYMONTH=1",
    "FREQ=YEARLY;BYDAY=20MO",
    "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29",
    "FREQ=YEARLY;BYMONTH=2,8;BYMONTHDAY=28,-2",
    "FREQ=YEARLY;BYMONTH=3;BYDAY=FR;BYSETPOS=-1",
)


def _plain(
    series: Series, window_from: datetime, window_to: datetime
) -> list[tuple[datetime, datetime]]:
    """`dateutil` from DTSTART without COUNT, then DTSTART and the matches after it,
    the first COUNT of them, RDATEs added, EXDATEs removed; overlapping the window,
    one per instant (the earlier recurrence id)."""
    assert series.rrule is not None
    parsed = parse_rule(series.rrule)
    text = ";".join(p for p in series.rrule.split(";") if not p.startswith("COUNT="))
    dtstart = series.start
    if parsed.freq == "WEEKLY" and parsed.bysetpos:  # BYSETPOS counts in the whole week
        dtstart = datetime.combine(week_start(dtstart.date(), parsed.wkst), dtstart.time())
    tzid = series.tzid or "UTC"
    stop = zones.wall(window_to, tzid) + timedelta(days=2)
    walls = [series.start]
    for wall in rrulestr(text, dtstart=dtstart):
        if wall > stop or (parsed.count is not None and len(walls) >= parsed.count):
            break
        if wall > series.start:
            walls.append(wall)
    walls = list(islice(walls, parsed.count))
    found: dict[datetime, datetime] = {}
    for wall in sorted((set(walls) | set(series.rdates)) - set(series.exdates)):
        start = zones.localise(wall, tzid)
        end = start + series.duration
        if start < window_to and (end > window_from or (end == start >= window_from)):
            found.setdefault(start, wall)
    return sorted(found.items())


def _series(rng: random.Random, rule: str) -> Series | None:
    tzid = rng.choice(ZONES)
    day = rng.randint(1, 31) if rng.random() < 0.2 else rng.randint(1, 28)
    try:
        start = datetime(rng.randint(2000, 2024), rng.randint(1, 12), day)
    except ValueError:
        return None
    if tzid is not None:
        start = start.replace(hour=rng.choice((0, 2, 9, 23)), minute=rng.choice((0, 30)))
    duration = timedelta(days=1) if tzid is None else timedelta(minutes=rng.choice((0, 30, 90)))
    text = f"{rule};COUNT={rng.randint(20, 5000)}"
    try:
        plain = Series(start, duration, tzid, tzid is None, recurrence.check_rule(text))
        recurrence.check_series(plain)
    except (recurrence.SeriesInvalid, ValueError):
        return None
    begin = zones.localise(start, tzid or "UTC")
    near = recurrence.occurrences(plain, begin, begin + timedelta(days=3 * 366), limit=100_000)
    exdates = tuple(o.recurrence_id for o in rng.sample(near, min(len(near), rng.randint(0, 3))))
    rdates = tuple(start + timedelta(days=rng.randint(1, 9000)) for _ in range(rng.randint(0, 2)))
    return Series(start, duration, tzid, tzid is None, plain.rrule, rdates, exdates)


def _windows(rng: random.Random, series: Series) -> list[tuple[datetime, datetime]]:
    begin = zones.localise(series.start, series.tzid or "UTC")
    year = rng.randint(series.start.year + 1, 2040)
    change = rng.choice((datetime(year, 3, 20, tzinfo=UTC), datetime(year, 10, 20, tzinfo=UTC)))
    mid = begin + timedelta(days=rng.randint(30, 6000))
    return [
        (begin, begin + timedelta(days=40)),
        (mid, mid + timedelta(days=rng.choice((7, 42)))),
        (change, change + timedelta(days=21)),
    ]


def test_counted_series_jump_and_agree_with_the_plain_expansion() -> None:
    rng = random.Random(SEED)  # noqa: S311 - test data
    compared = jumped = landed = walked_rules = 0
    while compared < SERIES:
        rule = rng.choice(FIXED + WALKING)
        series = _series(rng, rule)
        if series is None:
            continue
        compared += 1
        for window_from, window_to in _windows(rng, series):
            counter = Counter()
            found = recurrence.occurrences(
                series, window_from, window_to, limit=100_000, counter=counter
            )
            expected = _plain(series, window_from, window_to)
            assert [(o.start, o.recurrence_id) for o in found] == expected, (series, window_from)
            jumped += counter.jumps
            landed += bool(counter.jumps and found)  # jumped, and still running there
            if rule in WALKING:
                assert counter.jumps == 0, (series, window_from)
                walked_rules += 1
    assert jumped > SERIES // 2
    assert landed > SERIES // 4
    assert walked_rules > 100


@pytest.mark.parametrize("rule", FIXED)
def test_a_far_window_of_a_counted_series_jumps(rule: str) -> None:
    series = Series(
        datetime(2001, 1, 1, 9), timedelta(hours=1), "Europe/Berlin", False, f"{rule};COUNT=5000"
    )
    counter = Counter()
    window = (datetime(2023, 3, 20, tzinfo=UTC), datetime(2023, 4, 10, tzinfo=UTC))
    found = recurrence.occurrences(series, *window, counter=counter)
    assert [(o.start, o.recurrence_id) for o in found] == _plain(series, *window)
    assert counter.jumps == 1
    assert counter.candidates < 1200  # the first block (at most two years) and the window's


@pytest.mark.parametrize("rule", WALKING)
def test_a_counted_series_whose_count_per_period_varies_keeps_walking(rule: str) -> None:
    series = Series(
        datetime(2001, 1, 1, 9), timedelta(hours=1), "Europe/Berlin", False, f"{rule};COUNT=5000"
    )
    counter = Counter()
    window = (datetime(2023, 3, 20, tzinfo=UTC), datetime(2023, 4, 10, tzinfo=UTC))
    found = recurrence.occurrences(series, *window, counter=counter)
    assert [(o.start, o.recurrence_id) for o in found] == _plain(series, *window)
    assert counter.jumps == 0


def test_a_counted_series_that_ended_before_the_window_shows_nothing() -> None:
    weekly = Series(
        datetime(2020, 1, 6, 9), timedelta(hours=1), "Europe/Berlin", False, "FREQ=WEEKLY;COUNT=10"
    )
    counter = Counter()
    assert (
        recurrence.occurrences(
            weekly,
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 2, 1, tzinfo=UTC),
            counter=counter,
        )
        == []
    )
    assert counter.candidates < 60


def _event(rule: str | None, start: datetime, **fields: object) -> CalendarEvent:
    fields.setdefault("exdates", [])
    return CalendarEvent(
        id=uuid.uuid4(),
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        tzid="Europe/Berlin",
        all_day=False,
        rrule=rule,
        rdates=[],
        organizer_type=PrincipalType.USER,
        organizer_id=uuid.uuid4(),
        **fields,
    )


def test_overrides_take_their_occurrence_after_a_counted_jump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`expansion.effective` with moved occurrences (overrides) and EXDATEs of counted
    series answers the same with the jump as without it."""
    rng = random.Random(SEED + 1)  # noqa: S311 - test data
    masters = [
        _event(
            "FREQ=WEEKLY;BYDAY=MO,TH;COUNT=3000",
            datetime(2016, 3, 7, 8, tzinfo=UTC),
            exdates=[datetime(2026, 11, 26, 9)],
        ),
        _event(
            "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;COUNT=900",
            datetime(2010, 1, 29, 15, tzinfo=UTC),
        ),
        _event("FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;COUNT=5000", datetime(2009, 6, 1, 7, tzinfo=UTC)),
    ]
    window = (datetime(2026, 10, 19, tzinfo=UTC), datetime(2026, 12, 7, tzinfo=UTC))
    plain = expansion.effective(
        masters, set(), *window, viewer_zone="Europe/Berlin", budget=Budget()
    )
    picked = rng.sample(plain, 6)
    taken = {(event.id, o.recurrence_id) for o, event in picked}
    moved = [
        _event(
            None, o.start + timedelta(hours=1), series_id=event.id, recurrence_id=o.recurrence_id
        )
        for o, event in picked[:3]
    ]
    rows = [*masters, *moved]

    def expand() -> list[tuple[datetime, uuid.UUID]]:
        budget = Budget()
        found = expansion.effective(
            rows, taken, *window, viewer_zone="Europe/Berlin", budget=budget
        )
        return sorted((o.start, event.id) for o, event in found)

    jumping = expand()
    monkeypatch.setattr(recurrence_jump, "counted_jump", lambda *_: None)
    monkeypatch.setattr(recurrence, "counted_jump", lambda *_: None)
    walking = expand()
    assert jumping == walking
    assert len(jumping) == len(plain) - 6 + 3
