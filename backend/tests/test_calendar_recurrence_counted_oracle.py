"""Counted series that jump, against the RFC oracle (review M10 task 3c, R3c-1).

`test_calendar_recurrence_counted.py` compares the jump with `dateutil` in windows
drawn anywhere, and the oracle test (`test_calendar_recurrence_oracle.py`) only reads
windows that begin at DTSTART, where nothing jumps. So neither pins what the jump
must get right: how many occurrences lie before the block it starts from, read at
the series' end (the last occurrence, and nothing after it), for every shape of rule
`recurrence_count.per_block` has to tell apart.

Passes at the reviewed head (3d204e8). It is a guard, not a red test: each rule of
`TRAPS` fails when the line of `recurrence_count` that makes it walk is dropped (the
mutants of the review), and the seeded test fails for an off-by-one in the skipped
count (`recurrence_jump.counted_jump`).
"""

import random
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_jump import Counter
from app.modules.calendars.recurrence_rule import WEEKDAYS, Freq, parse_rule
from tests.test_calendar_recurrence_oracle import expected

SEED = 20261119
RULES = 500
HOUR = timedelta(hours=1)
LAST = date(2390, 12, 31)  # the oracle's last day; series lie in 1900 to 2399
# Rules whose count per period varies though a part of them looks fixed: each must
# walk, or count exactly. One per condition of `per_block`.
TRAPS = (
    "FREQ=WEEKLY;BYMONTH=1,6;BYDAY=MO,TH",  # weeks outside the months hold none
    "FREQ=WEEKLY;INTERVAL=2;BYMONTH=2",
    "FREQ=DAILY;BYMONTHDAY=31",
    "FREQ=DAILY;BYMONTHDAY=1,15;BYDAY=MO,TU,WE,TH,FR",
    "FREQ=DAILY;BYMONTH=2,3;BYDAY=MO",
    "FREQ=MONTHLY;BYDAY=1MO,2TU;BYMONTHDAY=1,2,8,9,10",  # both must hold: 0 to 2
    "FREQ=MONTHLY;BYDAY=MO,TU;BYMONTHDAY=1,2,3;BYSETPOS=1,2",  # a set of 0 to 2
    "FREQ=MONTHLY;BYMONTH=1,2,3;BYDAY=1MO",
    "FREQ=MONTHLY;BYDAY=4MO,-1MO",  # the fourth is the last in a month of four
    "FREQ=MONTHLY;BYDAY=TU;BYSETPOS=4,-1",
    "FREQ=MONTHLY;BYMONTHDAY=29",
    "FREQ=MONTHLY;BYMONTHDAY=14,-15",  # one day in February of a common year
    "FREQ=YEARLY;BYMONTH=3;BYDAY=1FR,2FR,3FR;BYSETPOS=1,-1",
    "FREQ=YEARLY;BYMONTH=1,2;BYDAY=1MO,2MO;BYMONTHDAY=1,2,3,8,9",
    "FREQ=YEARLY;BYDAY=1MO,-1FR,53MO",  # numbered in the year: a 53rd Monday is rare
    "FREQ=YEARLY;BYDAY=MO",
    "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29,-1",  # one day in a leap year, two never
    "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=28,-1",
    "FREQ=YEARLY;INTERVAL=3;BYMONTHDAY=30",
    "FREQ=YEARLY;BYMONTH=4,5;BYMONTHDAY=31",
)
STARTS = (datetime(2019, 12, 31, 9), datetime(2020, 2, 29, 9), datetime(2022, 1, 3, 9))


def _wrong(text: str, start: datetime, rng: random.Random) -> tuple[list[str], int]:
    """Where the series differs from the oracle around its end and at a day drawn from
    it, and how many of those windows jumped."""
    series = Series(start, HOUR, "UTC", False, text)
    every = expected(parse_rule(text), start.date(), LAST)
    wrong, jumps = [], 0
    for pivot in (every[-1], rng.choice(every)):
        first = pivot - timedelta(days=rng.randint(0, 30))
        last = min(pivot + timedelta(days=rng.choice([2, 40, 400])), LAST)
        window = (datetime.combine(first, time(), UTC), datetime.combine(last, time(), UTC))
        counter = Counter()
        found = recurrence.occurrences(series, *window, limit=10**6, counter=counter)
        jumps += counter.jumps
        if [o.recurrence_id.date() for o in found] != [d for d in every if first <= d < last]:
            wrong.append(f"{text} from {start:%a %Y-%m-%d} in {first} to {last}")
    return wrong, jumps


@pytest.mark.parametrize("rule", TRAPS)
def test_a_rule_whose_count_per_period_varies_ends_where_the_oracle_ends(rule: str) -> None:
    rng = random.Random(SEED)
    for start in STARTS:
        for count in (2, 37, 300):
            text = recurrence.check_rule(f"{rule};COUNT={count}")
            try:
                recurrence.check_series(Series(start, HOUR, "UTC", False, text))
            except recurrence.RuleInvalid:
                continue
            wrong, _ = _wrong(text, start, rng)
            assert wrong == []


def _rule_text(rng: random.Random) -> str:
    freq = rng.choice(list(Freq))
    parts = [f"FREQ={freq}", f"COUNT={rng.choice([rng.randint(2, 40), rng.randint(40, 600)])}"]
    if rng.random() < 0.5:
        parts.append(f"INTERVAL={rng.choice([2, 3, 4, 5, 7, 12, 14])}")
    by_month = rng.random() < 0.25
    if by_month:
        parts.append("BYMONTH=" + ",".join(map(str, rng.sample(range(1, 13), rng.randint(1, 4)))))
    if freq is not Freq.WEEKLY and rng.random() < 0.35:
        days = rng.sample([*range(1, 32), *range(-31, 0)], rng.randint(1, 3))
        parts.append("BYMONTHDAY=" + ",".join(map(str, days)))
    if rng.random() < 0.55:
        numbered = freq in (Freq.MONTHLY, Freq.YEARLY)
        top = 5 if freq is Freq.MONTHLY or by_month else 53
        share = rng.choice([0.0, 0.5, 1.0, 1.0])
        days = {
            (
                str(rng.choice([1, 2, 3, 4, -1, -2, -3, -4, top, -top]))
                if numbered and rng.random() < share
                else ""
            )
            + rng.choice(WEEKDAYS)
            for _ in range(rng.randint(1, 4))
        }
        parts.append("BYDAY=" + ",".join(sorted(days)))
    if rng.random() < 0.3:
        positions = [1, -1] if freq is Freq.DAILY else [1, 2, 3, 4, 5, 8, 9, -1, -2, -4, -5, -8]
        parts.append("BYSETPOS=" + ",".join(map(str, rng.sample(positions, rng.randint(1, 2)))))
    if rng.random() < 0.4:
        parts.append("WKST=" + rng.choice(WEEKDAYS))
    return ";".join(parts)


def test_counted_series_agree_with_the_rfc_oracle_at_their_end() -> None:
    rng = random.Random(SEED)
    checked, jumped, divergent = 0, 0, []
    while checked < RULES:
        try:
            text = recurrence.check_rule(_rule_text(rng))
            day = rng.choice([rng.randint(1, 28), 29, 30, 31])
            start = datetime(rng.randint(1990, 2300), rng.randint(1, 12), day, 9)
            recurrence.check_series(Series(start, HOUR, "UTC", False, text))
        except ValueError:  # a refused rule or series, the 31st of a short month
            continue
        wrong, jumps = _wrong(text, start, rng)
        divergent += wrong
        jumped += jumps
        checked += 1
    assert divergent == []
    assert jumped > RULES // 3  # the jump is what is read here
