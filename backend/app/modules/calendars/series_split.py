"""Splitting a series at an occurrence (plan M10 decision 6, I5): `scope=following`.

- The old series ends just before the split: its rule gets an `UNTIL` one second before
  the occurrence starts (all-day: the day before), also when it had a `COUNT`; its
  RDATEs and EXDATEs from the split on leave it.
- The new series starts at the split occurrence with a UID of its own and the old
  one's content and organiser (then the change): a counted rule keeps the rest (the
  old count minus the occurrences before the split, deleted ones counted, so the total
  stays); an `UNTIL` or endless rule stays as it was. RDATEs, EXDATEs and overrides
  from the split on move to it (along with its start if the change moves it,
  `series_rebase.rebase`); `CARRY` copies what hangs on the series (Task 4: attendees
  and their answers, Task 6: reminders).
- Splitting at the first occurrence is `scope=all` (the caller decides that).
- `truncate` (deleting this and the following) ends the old series the same way and
  makes its later overrides tombstones.
"""

import dataclasses
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.calendars import recurrence
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from app.modules.calendars.event_times import Checked, Times, check, times_of
from app.modules.calendars.event_writes import (
    CONTENT_FIELDS,
    CREATED,
    UPDATED,
    Change,
    announce,
    changed_fields,
    new_uid,
    snapshot,
    tombstone,
)
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_series import instant
from app.modules.calendars.series import Edited
from app.modules.calendars.series_rebase import (
    move_overrides,
    occurrence_times,
    rebase,
    safely,
    store_times,
    stored_series,
)

# What hangs on a series and goes along to the part split off: (session, old, new).
type Carry = Callable[[AsyncSession, CalendarEvent, CalendarEvent], Awaitable[None]]
CARRY: list[Carry] = []


def until_before(series: Series, wall: datetime) -> str | None:
    """The series' rule ending just before its occurrence `wall`: `UNTIL` one second
    before it starts (all-day: the day before), in place of a `COUNT`."""
    rule = series.rule
    if rule is None:
        return None
    until: date | datetime
    if series.all_day:
        until = wall.date() - timedelta(days=1)
    else:
        until = instant(series, wall) - timedelta(seconds=1)
    if rule.until is not None and type(rule.until) is type(until) and rule.until < until:
        until = rule.until
    return dataclasses.replace(rule, count=None, until=until).text


def rule_after(series: Series, wall: datetime) -> str | None:
    """The rule of the part from the occurrence `wall` on: a counted one keeps the
    rest (deleted occurrences count), any other stays; None when nothing is left."""
    rule = series.rule
    if rule is None or rule.count is None:
        return rule.text if rule else None
    rest = rule.count - safely(recurrence.count_before, series, wall)
    return dataclasses.replace(rule, count=rest).text if rest > 0 else None


def _old_part(event: CalendarEvent, series: Series, wall: datetime, zone: str) -> Checked:
    times = dataclasses.replace(
        times_of(event),
        rrule=until_before(series, wall),
        rdates=tuple(d for d in series.rdates if d < wall),
        exdates=tuple(d for d in series.exdates if d < wall),
    )
    return check(times, zone)


def _new_base(series: Series, wall: datetime) -> Times:
    return dataclasses.replace(
        occurrence_times(series, wall),
        rrule=rule_after(series, wall),
        rdates=tuple(d for d in series.rdates if d >= wall),
        exdates=tuple(d for d in series.exdates if d >= wall),
    )


async def split(
    session: AsyncSession,
    actor: Actor,
    event: CalendarEvent,
    wall: datetime,
    change: Change,
    *,
    dry_run: bool,
) -> Edited:
    """Splits the series `event` at its occurrence `wall` (not its first); the answer
    shows the new series."""
    repo = EventRepository(session, event.org_id)
    zone = await repo.calendar_zone(event.calendar_id)
    series = stored_series(event)
    old = _old_part(event, series, wall, zone)
    carried = await repo.overrides_of(event.id, since=wall)
    rebased = rebase(_new_base(series, wall), wall, change.values, carried, zone)
    if dry_run:
        return Edited(event, [], rebased.counts())
    content = {name: getattr(event, name) for name in CONTENT_FIELDS} | change.content()
    new = CalendarEvent(
        org_id=event.org_id,
        calendar_id=event.calendar_id,
        space_id=event.space_id,
        uid=new_uid(),
        organizer_type=event.organizer_type,
        organizer_id=event.organizer_id,
        version=1,
        **content,
    )
    store_times(new, rebased.checked)
    await repo.add(new)  # a new UID is free
    before = snapshot(event)
    store_times(event, old)
    event.version += 1
    await session.flush()
    await move_overrides(session, rebased, to=new)
    for carry in CARRY:
        await carry(session, event, new)
    await announce(session, actor, event, UPDATED, changed_fields(before, event))
    await announce(session, actor, new, CREATED)
    return Edited(new, sorted(change.values), rebased.counts())


async def truncate(
    session: AsyncSession, actor: Actor, event: CalendarEvent, wall: datetime
) -> Edited:
    """Deletes the occurrence `wall` (not the first) and every later one of `event`."""
    repo = EventRepository(session, event.org_id)
    zone = await repo.calendar_zone(event.calendar_id)
    old = _old_part(event, stored_series(event), wall, zone)
    for override in await repo.overrides_of(event.id, since=wall):
        tombstone(override)
    before = snapshot(event)
    store_times(event, old)
    event.version += 1
    await session.flush()
    fields = changed_fields(before, event)
    await announce(session, actor, event, UPDATED, fields)
    return Edited(event, fields)
