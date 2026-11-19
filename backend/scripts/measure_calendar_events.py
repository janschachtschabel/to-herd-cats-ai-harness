"""The rows of the calendar's expansion measurement (plan M10 Task 3c): series, single
events, birthdays and March series as `calendar_event` rows, each through
`event_times.check` as the API stores it. Pure; `measure_calendar_seed` inserts them."""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from uuid_utils.compat import uuid7

from app.core.errors import ValidationFailed
from app.core.principal import PrincipalType
from app.modules.calendars import zones
from app.modules.calendars.event_models import EventStatus, EventVisibility
from app.modules.calendars.event_times import Times, check
from app.modules.calendars.models import Calendar

ANCHOR = datetime(2026, 11, 23, tzinfo=UTC)  # a Monday
ZONE = "Europe/Berlin"
ZONES = (ZONE,) * 8 + ("America/New_York", "Asia/Tokyo")
# (weight, rule, minutes): the mixture of series.
RULES: tuple[tuple[int, str, int], ...] = (
    (4, "FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR", 15),
    (2, "FREQ=DAILY", 30),
    (20, "FREQ=WEEKLY", 60),
    (10, "FREQ=WEEKLY;INTERVAL=2", 60),
    (6, "FREQ=WEEKLY;BYDAY=TU,TH", 45),
    (12, "FREQ=MONTHLY;BYDAY=1MO", 90),
    (8, "FREQ=MONTHLY;BYMONTHDAY=15", 60),
    (5, "FREQ=MONTHLY;BYDAY=-1FR", 60),
    (5, "FREQ=MONTHLY;INTERVAL=3;BYDAY=2WE", 120),
    (10, "YEARLY_ALL_DAY", 0),
    (3, "FREQ=YEARLY", 60),
    (5, "RDATES", 60),
)


def _row(
    org_id: uuid.UUID, calendar: Calendar, organiser: uuid.UUID, times: Times, **extra: Any
) -> dict[str, Any]:
    checked = check(times, ZONE)
    return {
        "id": uuid7(),
        "org_id": org_id,
        "calendar_id": calendar.id,
        "space_id": calendar.space_id,
        "uid": f"{uuid7()}@messung.example",
        "title": "Termin",
        "all_day": times.all_day,
        "starts_at": checked.starts_at,
        "ends_at": checked.ends_at,
        "tzid": checked.tzid,
        "rrule": checked.rrule,
        "rdates": list(checked.rdates),
        "exdates": list(checked.exdates),
        "recurs_until": checked.recurs_until,
        "status": EventStatus.CONFIRMED,
        "visibility": EventVisibility.DEFAULT,
        "busy": not times.all_day,
        "organizer_type": PrincipalType.USER,
        "organizer_id": organiser,
        "version": 1,
        **extra,
    }


def _flags(rng: random.Random) -> dict[str, Any]:
    roll = rng.random()
    status = (
        EventStatus.TENTATIVE
        if roll < 0.05
        else EventStatus.CANCELLED
        if roll < 0.08
        else EventStatus.CONFIRMED
    )
    visibility = EventVisibility.PRIVATE if rng.random() < 0.1 else EventVisibility.DEFAULT
    return {"status": status, "visibility": visibility}


def _timed(rng: random.Random, day: date, minutes: int, zone: str) -> tuple[datetime, datetime]:
    wall = datetime(day.year, day.month, day.day, rng.randint(7, 17), rng.choice((0, 15, 30, 45)))
    start = zones.localise(wall, zone)
    return start, start + timedelta(minutes=minutes)


def series_rows(
    rng: random.Random, org_id: uuid.UUID, calendar: Calendar, organiser: uuid.UUID
) -> list[dict[str, Any]]:
    """One series (and, for some weekly ones, an override of an occurrence near the
    anchor)."""
    _, rule, minutes = rng.choices(RULES, weights=[w for w, _, _ in RULES])[0]
    day = (ANCHOR - timedelta(days=rng.randint(7, 5 * 365))).date()
    ending = rng.choice(("endless", "until", "count"))
    zone = rng.choice(ZONES)
    if rule == "YEARLY_ALL_DAY":
        until = (
            ""
            if ending != "until"
            else f";UNTIL={(ANCHOR + timedelta(days=rng.randint(-900, 900))).date():%Y%m%d}"
        )
        count = f";COUNT={rng.randint(3, 40)}" if ending == "count" else ""
        times = Times(all_day=True, first_day=day, last_day=day, rrule=f"FREQ=YEARLY{until}{count}")
        return [_row(org_id, calendar, organiser, times, **_flags(rng))]
    start, end = _timed(rng, day, minutes, zone)
    if rule == "RDATES":
        wall = zones.wall(start, zone)
        rdates = tuple(wall + timedelta(days=rng.randint(1, 5 * 365)) for _ in range(6))
        return [
            _row(
                org_id,
                calendar,
                organiser,
                Times(starts_at=start, ends_at=end, tzid=zone, rdates=rdates),
                **_flags(rng),
            )
        ]
    if ending == "until":
        last = max(ANCHOR + timedelta(days=rng.randint(-900, 900)), start + timedelta(days=30))
        rule += f";UNTIL={last.astimezone(UTC):%Y%m%dT%H%M%SZ}"
    elif ending == "count":
        rule += f";COUNT={rng.randint(5, 300)}"
    wall = zones.wall(start, zone)
    weekly = rule.startswith("FREQ=WEEKLY") and "INTERVAL" not in rule and "BYDAY" not in rule
    exdates = (
        tuple(wall + timedelta(weeks=rng.randint(1, 200)) for _ in range(3))
        if weekly and rng.random() < 0.3
        else ()
    )
    times = Times(starts_at=start, ends_at=end, tzid=zone, rrule=rule, exdates=exdates)
    master = _row(org_id, calendar, organiser, times, **_flags(rng))
    rows = [master]
    if weekly and ending == "endless" and rng.random() < 0.4:
        weeks = (ANCHOR.date() - wall.date()).days // 7 + rng.randint(-5, 10)
        taken = wall + timedelta(weeks=weeks)
        moved = zones.localise(taken + timedelta(hours=2), zone)
        override = Times(starts_at=moved, ends_at=moved + timedelta(minutes=minutes), tzid=zone)
        rows.append(
            _row(
                org_id,
                calendar,
                organiser,
                override,
                uid=master["uid"],
                series_id=master["id"],
                recurrence_id=taken,
            )
        )
    return rows


def single_row(
    rng: random.Random, org_id: uuid.UUID, calendar: Calendar, organiser: uuid.UUID
) -> dict[str, Any]:
    day = (ANCHOR + timedelta(days=rng.randint(-365, 365))).date()
    if rng.random() < 0.08:
        times = Times(all_day=True, first_day=day, last_day=day + timedelta(days=rng.randint(0, 2)))
    else:
        zone = rng.choice(ZONES)
        start, end = _timed(rng, day, rng.choice((30, 45, 60, 90, 120)), zone)
        times = Times(starts_at=start, ends_at=end, tzid=zone)
    return _row(org_id, calendar, organiser, times, **_flags(rng))


def birthday_row(
    rng: random.Random, org_id: uuid.UUID, calendar: Calendar, organiser: uuid.UUID
) -> dict[str, Any]:
    day = date(rng.randint(1950, 2005), 3, rng.randint(1, 31))
    times = Times(all_day=True, first_day=day, last_day=day, rrule="FREQ=YEARLY")
    return _row(org_id, calendar, organiser, times)


def march_row(
    rng: random.Random, org_id: uuid.UUID, calendar: Calendar, organiser: uuid.UUID
) -> dict[str, Any]:
    start, end = _timed(rng, date(rng.randint(2000, 2020), 3, rng.randint(1, 31)), 60, ZONE)
    return _row(
        org_id,
        calendar,
        organiser,
        Times(starts_at=start, ends_at=end, tzid=ZONE, rrule="FREQ=YEARLY"),
    )


def drawn(make: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """A series the API takes: a draw it refuses (an UNTIL before the start, say) is
    drawn again."""
    for _ in range(50):
        try:
            return make()
        except ValidationFailed:
            continue
    raise RuntimeError("no series drawn")
