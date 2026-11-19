"""Moving a series' pieces along with its start (plan M10 decision 6, I4 and I5): the
part of a change that `series.change_all` and `series_split.split` share.

`rebase` takes the times a series had (`base`, starting at the wall time `old_wall`)
and a change: when the start moves on the wall clock (09:00 → 10:00, another day; the
same wall time in another zone is no move), its EXDATEs, its RDATEs and the recurrence
id of each override move by the same wall-time difference, so deleted occurrences
stay deleted and overrides stay. An RDATE or EXDATE list the change names itself is
taken as named. Then whatever no longer names an occurrence of the new series is
dropped: overrides become tombstones, EXDATEs go (`Rebased.counts`).
`move_overrides` writes that, one override at a time in the order that keeps every
(UID, recurrence id) unique on the way.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendars import recurrence
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_times import (
    Checked,
    Times,
    check,
    invalid,
    overlay,
    series_of,
    wall_start,
)
from app.modules.calendars.event_writes import tombstone
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_jump import Counter
from app.modules.calendars.recurrence_series import instant

DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Dropped:
    overrides: int = 0
    exdates: int = 0


@dataclass(frozen=True, slots=True)
class Rebased:
    checked: Checked
    moved: list[tuple[CalendarEvent, datetime]]  # kept overrides, with their new id
    dropped: list[CalendarEvent]  # overrides that name no occurrence any more
    dropped_exdates: int

    def counts(self) -> Dropped:
        return Dropped(len(self.dropped), self.dropped_exdates)


def safely[T](compute: Callable[..., T], *args: Any) -> T:
    """`compute(*args)`; a series that cannot be (`SeriesInvalid`) is 422 with its code."""
    try:
        result: T = compute(*args)
    except recurrence.SeriesInvalid as exc:
        raise invalid(exc.code) from None
    return result


def stored_series(event: CalendarEvent) -> Series:
    return safely(series_of, event)


def until_of(event: CalendarEvent) -> datetime | None:
    """When the stored event's last occurrence ends (`recurs_until`; None: endless)."""
    if not event.recurring:
        return event.ends_at
    return safely(recurrence.last_end, stored_series(event))


def occurrence_times(series: Series, wall: datetime) -> Times:
    """The times of the series' occurrence `wall` as a client would send them."""
    start = instant(series, wall)
    if series.all_day:
        last = (start + series.duration - DAY).date()
        return Times(all_day=True, first_day=start.date(), last_day=last)
    return Times(starts_at=start, ends_at=start + series.duration, tzid=series.tzid)


def hits(series: Series, walls: Sequence[datetime]) -> set[datetime]:
    """Which of `walls` name an occurrence of the series (deleted ones too). A counted
    series or one without a rule is walked once (at most 5,500 occurrences); any other
    one jumps to each wall."""
    wanted = set(walls)
    if not wanted:
        return set()
    rule = series.rule
    if rule is None or rule.count is not None:
        lo, hi = min(wanted), max(wanted)
        named = recurrence.walls(series, lo, hi, Counter(), keep_exdates=True)
        return wanted & set(named)
    return {wall for wall in wanted if recurrence.is_occurrence(series, wall)}


def _shift(walls: Sequence[datetime], delta: timedelta) -> tuple[datetime, ...]:
    return tuple(safely(recurrence.shift, wall, delta) for wall in walls)


def rebase(
    base: Times,
    old_wall: datetime,
    values: Mapping[str, Any],
    overrides: Sequence[CalendarEvent],
    zone: str,
) -> Rebased:
    """The new times of a series that started at the wall time `old_wall` with `base`,
    after the change `values`: its pieces moved by the start's wall-time difference,
    and whatever no longer names an occurrence dropped."""
    times = overlay(base, values)
    delta = wall_start(times, zone) - old_wall
    move_exdates = "exdates" not in values
    if delta:
        if "rdates" not in values:
            times = replace(times, rdates=_shift(times.rdates, delta))
        if move_exdates:
            times = replace(times, exdates=_shift(times.exdates, delta))
    checked = check(times, zone)
    moved = [
        (override, safely(recurrence.shift, override.recurrence_id, delta))
        for override in overrides
        if override.recurrence_id is not None
    ]
    candidates = [wall for _, wall in moved] + (list(checked.exdates) if move_exdates else [])
    found = safely(hits, checked.series, candidates)
    kept = tuple(e for e in checked.exdates if not move_exdates or e in found)
    dropped_exdates = len(checked.exdates) - len(kept)
    if dropped_exdates:
        checked = check(replace(times, exdates=kept), zone)
    return Rebased(
        checked=checked,
        moved=[(o, wall) for o, wall in moved if wall in found],
        dropped=[o for o, wall in moved if wall not in found],
        dropped_exdates=dropped_exdates,
    )


def store_times(event: CalendarEvent, checked: Checked) -> None:
    event.all_day = checked.series.all_day
    event.starts_at = checked.starts_at
    event.ends_at = checked.ends_at
    event.tzid = checked.tzid
    event.rrule = checked.rrule
    event.rdates = list(checked.rdates)
    event.exdates = list(checked.exdates)
    event.recurs_until = checked.recurs_until


async def move_overrides(
    session: AsyncSession, rebased: Rebased, *, to: CalendarEvent | None = None
) -> None:
    """Drops what `rebased` drops and gives the kept overrides their new recurrence id
    (and, with `to`, the new series and its UID). One at a time, in the order that
    keeps every (UID, recurrence id) unique on the way."""
    for override in rebased.dropped:
        tombstone(override)
    await session.flush()
    rising = any(wall > (o.recurrence_id or wall) for o, wall in rebased.moved)
    for override, wall in sorted(
        rebased.moved, key=lambda moved: moved[0].recurrence_id or datetime.min, reverse=rising
    ):
        if wall == override.recurrence_id and to is None:
            continue
        override.recurrence_id = wall
        if to is not None:
            override.series_id, override.uid = to.id, to.uid
        override.version += 1
        await session.flush()
