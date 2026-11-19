"""What a change's times do to an occurrence, carried to another one (plan M10 task 3b,
ruling 6; review M10 task 3b, R3b-3 and R3b-7): pure, no database.

A change names the times of the occurrence the client had open (`scope=following`:
the split occurrence). Its **effect** is the move of that occurrence's start on the
wall clock, the new length, zone and kind (all-day or not). The same effect is applied
where the change lands elsewhere: at the anchor a new part starts at, at each stray
occurrence that stays with the old part, at DTSTART when "this and the following"
starts at the first live occurrence. A change that does not move the start (no new
start, zone or kind, or the occurrence's own start sent back) moves nothing, also for
an occurrence in a gap (whose start is not its wall time).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.modules.calendars import recurrence, zones
from app.modules.calendars.event_times import TIME_FIELDS, Times, check, overlay
from app.modules.calendars.recurrence import Series
from app.modules.calendars.series_rebase import occurrence_times, safely

DAY = timedelta(days=1)
SERIES_NAMES = ("rrule", "rdates", "exdates")


@dataclass(frozen=True, slots=True)
class Effect:
    delta: timedelta  # the start's move on the wall clock
    duration: timedelta
    tzid: str | None
    all_day: bool


def times_named(values: Mapping[str, Any]) -> dict[str, Any]:
    """The times of one occurrence a change names (not its rule or dates)."""
    return {k: v for k, v in values.items() if k in TIME_FIELDS and k not in SERIES_NAMES}


def effect_of(
    series: Series, wall: datetime, values: Mapping[str, Any], zone: str
) -> Effect | None:
    """The effect of the change `values` on the occurrence `wall`; None if it names no
    times. 422 as `event_times.check` answers."""
    named = times_named(values)
    if not named:
        return None
    base = occurrence_times(series, wall)
    new = check(overlay(base, named), zone).series
    stays = (
        new.all_day == series.all_day
        and new.tzid == series.tzid
        and named.get("starts_at", base.starts_at) == base.starts_at
        and named.get("first_day", base.first_day) == base.first_day
    )
    start = wall if stays else new.start
    return Effect(start - wall, new.duration, new.tzid, new.all_day)


def times_at(effect: Effect, wall: datetime) -> dict[str, Any]:
    """The times (API names) the effect gives the occurrence `wall`."""
    start = safely(recurrence.shift, wall, effect.delta)
    if effect.all_day:
        first = start.date()
        return {
            "all_day": True,
            "first_day": first,
            "last_day": first + (effect.duration // DAY - 1) * DAY,
        }
    at = zones.localise(start, effect.tzid or "")
    return {
        "all_day": False,
        "starts_at": at,
        "ends_at": at + effect.duration,
        "time_zone": effect.tzid,
    }


def moved_to(
    series: Series, wall: datetime, values: Mapping[str, Any], to: datetime, zone: str
) -> dict[str, Any]:
    """`values`, named for the occurrence `wall`, with its times as they land on the
    occurrence `to`."""
    effect = effect_of(series, wall, values, zone)
    if effect is None or to == wall:
        return dict(values)
    kept = {k: v for k, v in values.items() if k not in times_named(values)}
    return kept | times_at(effect, to)


def occurrence_after(series: Series, effect: Effect | None, wall: datetime) -> Times:
    """The times of the occurrence `wall` after the effect (unchanged without one)."""
    base = occurrence_times(series, wall)
    return base if effect is None else overlay(base, times_at(effect, wall))
