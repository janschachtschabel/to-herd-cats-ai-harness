"""The fast-forward (plan M10 decision 6, I7): a far window starts the rule whole
periods later instead of counting from DTSTART. It is our own code with no oracle in
the library, so it is compared with the plain expansion from DTSTART by `dateutil`."""

import random
from datetime import UTC, datetime, timedelta
from itertools import islice

import pytest
from dateutil.rrule import rrulestr

from app.modules.calendars import recurrence, zones
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_jump import Counter, jump
from app.modules.calendars.recurrence_rule import parse_rule

RULES = 400
ZONES = ("Europe/Berlin", "America/New_York", "Australia/Sydney", "Asia/Kolkata", "UTC", None)
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def _random_rule(rng: random.Random, all_day: bool) -> str:
    freq = rng.choice(("DAILY", "WEEKLY", "MONTHLY", "YEARLY"))
    parts = [f"FREQ={freq}"]
    if rng.random() < 0.5:
        parts.append(f"INTERVAL={rng.choice((2, 3, 4, 7, 12))}")
    ends = rng.random()
    if ends < 0.2:
        parts.append(f"COUNT={rng.randint(1, 300)}")
    elif ends < 0.45:
        until = datetime(
            rng.randint(2026, 2080), rng.randint(1, 12), rng.randint(1, 28), rng.randint(0, 23)
        )
        parts.append(
            "UNTIL=" + (until.strftime("%Y%m%d") if all_day else until.strftime("%Y%m%dT%H%M%SZ"))
        )
    by = False
    if freq in ("MONTHLY", "YEARLY") and rng.random() < 0.4:
        parts.append(
            f"BYMONTHDAY={','.join(str(rng.choice((1, 2, 15, 28, 29, 30, 31, -1, -2))) for _ in range(rng.randint(1, 2)))}"
        )
        by = True
    if rng.random() < 0.5:
        days = rng.sample(DAYS, rng.randint(1, 5))
        if freq in ("MONTHLY", "YEARLY") and rng.random() < 0.5:
            days = [f"{rng.choice((1, 2, -1, 3))}{d}" for d in days[:2]]
        parts.append(f"BYDAY={','.join(days)}")
        by = True
    if freq != "YEARLY" and rng.random() < 0.25 or freq == "YEARLY" and rng.random() < 0.6:
        months = sorted(set(rng.choice(range(1, 13)) for _ in range(rng.randint(1, 4))))
        parts.append(f"BYMONTH={','.join(map(str, months))}")
        by = True
    if by and freq != "DAILY" and rng.random() < 0.3:
        parts.append(f"BYSETPOS={rng.choice((1, -1, 2))}")
    if rng.random() < 0.4:
        parts.append(f"WKST={rng.choice(DAYS)}")
    return ";".join(parts)


def _random_series(rng: random.Random) -> Series | None:
    tzid = rng.choice(ZONES)
    all_day = tzid is None
    start = datetime(rng.randint(2000, 2030), rng.randint(1, 12), rng.randint(1, 28))
    if not all_day:
        start = start.replace(hour=rng.choice((0, 2, 9, 23)), minute=rng.choice((0, 30)))
    text = _random_rule(rng, all_day)
    try:
        series = Series(
            start=start,
            duration=timedelta(days=rng.randint(1, 3))
            if all_day
            else timedelta(minutes=rng.choice((0, 30, 90, 600))),
            tzid=tzid,
            all_day=all_day,
            rrule=recurrence.check_rule(text),
            rdates=tuple(
                start + timedelta(days=rng.randint(1, 4000)) for _ in range(rng.randint(0, 2))
            ),
            exdates=(),
        )
        recurrence.check_series(series)
    except recurrence.SeriesInvalid:
        return None
    # delete a few of its own first occurrences
    begin = zones.localise(series.start, tzid or "UTC")
    first = recurrence.occurrences(series, begin, begin + timedelta(days=400), limit=100_000)
    picked = rng.sample(first, min(len(first), rng.randint(0, 2)))
    return Series(
        series.start,
        series.duration,
        tzid,
        all_day,
        series.rrule,
        series.rdates,
        tuple(o.recurrence_id for o in picked),
    )


def _plain(
    series: Series, window_from: datetime, window_to: datetime
) -> list[tuple[datetime, datetime]]:
    """The plain expansion: `dateutil` from DTSTART, DTSTART as the first occurrence (RFC
    5545 3.8.5.3), UNTIL compared as an instant, RDATE added, EXDATE removed."""
    assert series.rrule is not None
    text, until = series.rrule, None
    if not series.all_day and "UNTIL=" in text:
        parts = text.split(";")
        until_text = next(p for p in parts if p.startswith("UNTIL="))[6:]
        until = datetime.strptime(until_text, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        text = ";".join(p for p in parts if not p.startswith("UNTIL="))
    rule = rrulestr(text, dtstart=series.start)
    rule_count = parse_rule(series.rrule).count
    tzid = series.tzid or "UTC"
    stop = zones.wall(window_to, tzid) + timedelta(days=2)
    walls: list[datetime] = [series.start]
    for wall in rule:
        if wall > stop:
            break
        if wall != series.start:
            walls.append(wall)
    if rule_count is not None:
        walls = list(islice(walls, rule_count))
    walls += list(series.rdates)
    found = set()
    for wall in set(walls) - set(series.exdates):
        start = zones.localise(wall, tzid)
        if (
            until is not None
            and start > until
            and wall not in series.rdates
            and wall != series.start
        ):
            continue
        end = start + series.duration
        if start < window_to and (end > window_from or (end == start and start >= window_from)):
            found.add((start, wall))
    return sorted(found)


def _windows(rng: random.Random, series: Series) -> list[tuple[datetime, datetime]]:
    near = zones.localise(series.start, series.tzid or "UTC") + timedelta(days=rng.randint(0, 90))
    far = datetime(rng.randint(2060, 2090), rng.randint(1, 12), 1, tzinfo=UTC)
    year = rng.randint(2030, 2050)
    change = rng.choice((datetime(year, 3, 1, tzinfo=UTC), datetime(year, 9, 25, tzinfo=UTC)))
    return [
        (near, near + timedelta(days=21)),
        (far, far + timedelta(days=31)),
        (change, change + timedelta(days=46)),
    ]


def test_fast_forward_equals_plain_expansion() -> None:
    rng = random.Random(20261118)
    compared = jumped = 0
    while compared < RULES:
        series = _random_series(rng)
        if series is None:
            continue
        compared += 1
        for window_from, window_to in _windows(rng, series):
            counter = Counter()
            fast = recurrence.occurrences(
                series, window_from, window_to, limit=100_000, counter=counter
            )
            plain = _plain(series, window_from, window_to)
            assert [(o.start, o.recurrence_id) for o in fast] == plain, (series, window_from)
            assert all(o.end - o.start == series.duration for o in fast)
            jumped += counter.jumps
    assert jumped > RULES // 2  # far windows of endless rules did jump


def test_a_window_far_ahead_of_an_endless_series_generates_few_candidates() -> None:
    daily = Series(
        datetime(2020, 1, 1, 9), timedelta(hours=1), "Europe/Berlin", False, "FREQ=DAILY", (), ()
    )
    window = (datetime(2040, 6, 1, tzinfo=UTC), datetime(2040, 6, 8, tzinfo=UTC))
    counter = Counter()
    found = recurrence.occurrences(daily, *window, counter=counter)
    assert len(found) == 7
    # one period before the window, the window's own seven, two slack days either side
    # (offsets of a zone differ by up to a day) and the one past the end that stops it
    assert counter.candidates <= 1 + 7 + 2 * 2 + 1
    assert counter.jumps == 1
    # a counted series cannot jump: it is counted from DTSTART, and stays right
    counted = Series(
        datetime(2020, 1, 1, 9),
        timedelta(hours=1),
        "Europe/Berlin",
        False,
        "FREQ=DAILY;COUNT=5000",
        (),
        (),
    )
    counter = Counter()
    found = recurrence.occurrences(
        counted,
        datetime(2033, 9, 1, tzinfo=UTC),
        datetime(2033, 9, 15, tzinfo=UTC),
        counter=counter,
    )
    assert [o.recurrence_id.date().isoformat() for o in found] == [
        "2033-09-01",
        "2033-09-02",
        "2033-09-03",
        "2033-09-04",
        "2033-09-05",
        "2033-09-06",
        "2033-09-07",
        "2033-09-08",
    ]  # the 5,000th is 8 September 2033
    assert counter.jumps == 0
    assert counter.candidates >= 4999


@pytest.mark.parametrize(
    ("rule", "start", "window_from", "jumped"),
    [
        (
            "FREQ=DAILY;INTERVAL=3",
            datetime(2026, 1, 1, 9),
            datetime(2026, 1, 11),
            datetime(2026, 1, 10, 9),
        ),
        # weeks begin on WKST; the week of 10 June 2026 (a Wednesday) begins on Sunday 7 June
        (
            "FREQ=WEEKLY;WKST=SU;BYDAY=MO",
            datetime(2026, 1, 5, 9),
            datetime(2026, 6, 10),
            datetime(2026, 6, 7, 9),
        ),
        (
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO",
            datetime(2026, 1, 5, 9),
            datetime(2026, 1, 28),
            datetime(2026, 1, 19, 9),
        ),
        (
            "FREQ=MONTHLY;INTERVAL=5;BYMONTHDAY=31",
            datetime(2026, 1, 31, 9),
            datetime(2027, 1, 1),
            datetime(2026, 11, 1, 9),
        ),
        (
            "FREQ=YEARLY;INTERVAL=4",
            datetime(2024, 2, 29, 9),
            datetime(2041, 3, 1),
            datetime(2040, 1, 1, 9),
        ),
        (
            "FREQ=DAILY;COUNT=10",
            datetime(2026, 1, 1, 9),
            datetime(2030, 1, 1),
            datetime(2026, 1, 1, 9),
        ),
        ("FREQ=DAILY", datetime(2026, 1, 1, 9), datetime(2025, 1, 1), datetime(2026, 1, 1, 9)),
    ],
)
def test_jump_moves_whole_periods(
    rule: str, start: datetime, window_from: datetime, jumped: datetime
) -> None:
    assert jump(parse_rule(rule), start, window_from) == jumped
