"""The write path of an event named by id (plan M10 task 3b): locking it and choosing
what its scope does. `events.EventService.update`/`delete` run the checks around it.

- `lock_for_write`: the event found by id, locked and read afresh, after the series it
  belongs to **then** (review M10 task 3b, R3b-9): a split between the read and the
  lock re-homes an override, so the locks are taken in a savepoint and taken again in
  the same order with the series read under the lock; after `LOCK_TRIES` changes in a
  row, 409 `event.version_conflict`. A series is always locked before its overrides.
- `edit`: `scope=all` changes the row (an override takes no rule or dates), `this`
  adds an override, `following` splits; "this and the following" from the first live
  occurrence is `all`, with the change's times carried to the series' start
  (`series_effect.moved_to`; review M10 task 3b, R3b-7).
- `remove`: `all` makes the series and its overrides tombstones (an override: its
  occurrence an EXDATE), `this` an EXDATE, `following` ends the series (from the first
  live occurrence: all).
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import Conflict, NotFound
from app.modules.calendars import series, series_split
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from app.modules.calendars.event_times import invalid
from app.modules.calendars.event_writes import Change, Scope
from app.modules.calendars.series import Edited, end_series
from app.modules.calendars.series_cut import first_live
from app.modules.calendars.series_effect import moved_to
from app.modules.calendars.series_rebase import stored_series

LOCK_TRIES = 3


def event_not_found() -> NotFound:
    return NotFound(code="event.not_found")


async def lock_for_write(session: AsyncSession, found: CalendarEvent) -> CalendarEvent:
    """`found`, locked and read afresh after the series it belongs to under the lock."""
    repo = EventRepository(session, found.org_id)
    event_id, series_id = found.id, found.series_id
    for _ in range(LOCK_TRIES):
        savepoint = await session.begin_nested()
        if series_id is not None:
            await repo.lock(series_id)
        locked = await repo.lock(event_id)
        now = series_id if locked is None else locked.series_id
        if now == series_id:
            await savepoint.commit()
            if locked is None:  # deleted meanwhile
                raise event_not_found()
            return locked
        await savepoint.rollback()  # releases the locks taken in it
        series_id = now
    raise Conflict("The event changed meanwhile", code="event.version_conflict")


def occurrence(event: CalendarEvent, text: str | None) -> datetime:
    """The named occurrence of a series; `this` and `following` need a series."""
    if not event.recurring or event.series_id is not None:
        raise invalid("event.scope_invalid")
    return series.occurrence_of(event, text)


async def edit(
    session: AsyncSession,
    actor: Actor,
    event: CalendarEvent,
    change: Change,
    scope: Scope,
    named: str | None,
    dry_run: bool,
) -> Edited:
    if scope is Scope.ALL:
        if event.series_id is not None and change.names_series():
            raise invalid("event.scope_invalid")  # an override is no series
        return await series.change_all(session, actor, event, change, dry_run=dry_run)
    wall = occurrence(event, named)
    if scope is Scope.THIS:
        return await series.override(session, actor, event, wall, change, dry_run=dry_run)
    stored = stored_series(event)
    if wall == first_live(stored):  # this and the following from the first: all
        if wall != stored.start:
            zone = await EventRepository(session, event.org_id).calendar_zone(event.calendar_id)
            change = Change(moved_to(stored, wall, change.values, stored.start, zone))
        return await series.change_all(session, actor, event, change, dry_run=dry_run)
    return await series_split.split(session, actor, event, wall, change, dry_run=dry_run)


async def remove(
    session: AsyncSession, actor: Actor, event: CalendarEvent, scope: Scope, named: str | None
) -> Edited:
    if event.series_id is not None and event.recurrence_id is not None:
        if scope is not Scope.ALL:
            raise invalid("event.scope_invalid")
        master = await EventRepository(session, event.org_id).lock(event.series_id)
        if master is None:  # cannot be: the series' tombstone takes its overrides
            raise event_not_found()
        # Deleting an override deletes its occurrence (an EXDATE; it a tombstone).
        return await series.delete_one(session, actor, master, event.recurrence_id)
    if scope is not Scope.ALL:
        wall = occurrence(event, named)
        if scope is Scope.THIS:
            return await series.delete_one(session, actor, event, wall)
        if wall != first_live(stored_series(event)):
            return await series_split.truncate(session, actor, event, wall)
    return Edited(event, [], reached=await end_series(session, actor, event, ()))
