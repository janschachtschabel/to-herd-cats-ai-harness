"""Changing a series (plan M10 decision 6, I4 and I6): the whole of it, one occurrence,
or one occurrence deleted. Splitting it is `series_split`.

- Occurrences are named by their wall time in the series' zone (`recurrence_id`, the
  window's `OccurrenceOut.recurrence_id`); `occurrence_of` takes one back (422
  `event.occurrence_required`/`event.occurrence_unknown`; a deleted one is unknown).
- `change_all` (`scope=all`) changes the row itself. A series' pieces move with its
  start and what no longer names an occurrence is dropped (`series_rebase.rebase`; an
  override whose occurrence an EXDATE deletes too); the answer counts it (`Dropped`),
  and `dry_run` only counts. Its content reaches its overrides (`series_reach.spread`:
  each field an override did not change itself; private and cancelled everywhere).
- `override` (`scope=this`) adds an override: a row of its own with the series' UID,
  content and organiser, at the occurrence's time unless the change names another; it
  is no series (naming `rrule`, `rdates` or `exdates` is 422 `event.scope_invalid`).
  An occurrence with an override already answers 409 `event.occurrence_overridden`,
  in a dry run too (review M10 task 3b, R3b-10). A new override leaves the series'
  version as it is (ruling 11). The hooks `ON_OVERRIDE` run for it (Task 4: copy the
  series' attendees and answers).
- `delete_one` (`scope=this` on delete, or deleting an override) adds an EXDATE (at most
  500, 422 `event.too_many_dates`) and makes the occurrence's override a tombstone.
- A series with no live occurrence left becomes a tombstone with its overrides
  (review M10 task 3b, R3b-7).
- `Edited.reached` names the existing overrides a change writes (or, in a dry run,
  would); the caller checks the writer's full sight of each (`series_reach`, R3b-1).
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import Conflict
from app.modules.calendars import recurrence
from app.modules.calendars.event_models import DATES_MAX, CalendarEvent
from app.modules.calendars.event_repository import EventRepository, UidTaken
from app.modules.calendars.event_times import (
    TIME_FIELDS,
    Checked,
    check,
    invalid,
    overlay,
    times_of,
)
from app.modules.calendars.event_writes import (
    CONTENT_FIELDS,
    CREATED,
    DELETED,
    UPDATED,
    Change,
    announce,
    changed_fields,
    snapshot,
    stored_names,
    tombstone,
)
from app.modules.calendars.series_cut import first_live
from app.modules.calendars.series_reach import apply, spread
from app.modules.calendars.series_rebase import (
    Dropped,
    Rebased,
    move_overrides,
    occurrence_times,
    rebase,
    safely,
    store_times,
    stored_series,
    until_of,
)

# What hangs on a series and goes along to a new override: (session, series, override).
type OnOverride = Callable[[AsyncSession, CalendarEvent, CalendarEvent], Awaitable[None]]
ON_OVERRIDE: list[OnOverride] = []


@dataclass(frozen=True, slots=True)
class Edited:
    """What a change wrote: the event the answer shows, the stored fields it changed,
    what it dropped, the existing overrides it wrote (or would), and whether it wrote
    anything at all (a change to what is already there writes nothing)."""

    event: CalendarEvent
    fields: list[str]
    dropped: Dropped = Dropped()
    reached: tuple[CalendarEvent, ...] = ()
    wrote: bool = True


def occurrence_of(event: CalendarEvent, text: str | None) -> datetime:
    """The occurrence of the series `event` that `text` names (its wall time, ISO 8601
    without offset), deleted ones excluded."""
    if not text:
        raise invalid("event.occurrence_required")
    try:
        wall = datetime.fromisoformat(text)
    except ValueError:
        raise invalid("event.occurrence_unknown") from None
    if wall.tzinfo is not None or wall.microsecond:
        raise invalid("event.occurrence_unknown")
    series = stored_series(event)
    if wall in series.exdates or not safely(recurrence.is_occurrence, series, wall):
        raise invalid("event.occurrence_unknown")
    return wall


def _unique(events: Sequence[CalendarEvent]) -> tuple[CalendarEvent, ...]:
    return tuple({event.id: event for event in events}.values())


async def end_series(
    session: AsyncSession, actor: Actor, series: CalendarEvent, reached: Sequence[CalendarEvent]
) -> tuple[CalendarEvent, ...]:
    """Makes the series and every live override a tombstone; the overrides written."""
    rest = await EventRepository(session, series.org_id).overrides_of(series.id)
    for override in rest:
        tombstone(override)
    tombstone(series)
    await session.flush()
    written = _unique([*reached, *rest])
    await announce(session, actor, series, DELETED, overrides=written)
    return written


async def change_all(
    session: AsyncSession, actor: Actor, event: CalendarEvent, change: Change, *, dry_run: bool
) -> Edited:
    """`scope=all`: the row itself (a series, a single event or an override)."""
    repo = EventRepository(session, event.org_id)
    content = change.content()
    times = any(name in change.values for name in TIME_FIELDS)
    master = event.series_id is None
    overrides = await repo.overrides_of(event.id) if master and (times or content) else []
    rebased: Rebased | None = None
    if times:
        zone = await repo.calendar_zone(event.calendar_id)
        rebased = rebase(
            times_of(event), stored_series(event).start, change.values, overrides, zone
        )
    before = snapshot(event)
    kept = [o for o in overrides if rebased is None or o not in rebased.dropped]
    spreading = spread(before, content, kept)
    reached = _unique([*(rebased.written() if rebased else []), *(o for o, _ in spreading)])
    dropped = rebased.counts() if rebased else Dropped()
    empty = rebased is not None and event.recurring and first_live(rebased.checked.series) is None
    if dry_run:
        return Edited(event, [], dropped, _unique([*reached, *kept]) if empty else reached, False)
    for name, value in content.items():
        setattr(event, name, value)
    if rebased is not None:
        store_times(event, rebased.checked)
        await move_overrides(session, rebased)
    apply(spreading)
    fields = changed_fields(before, event)
    if empty:  # every occurrence deleted: the series goes (R3b-7)
        written = await end_series(session, actor, event, reached)
        return Edited(event, fields, dropped, written)
    if not (fields or reached):
        return Edited(event, [], dropped, (), wrote=False)
    event.version += 1
    await session.flush()
    await announce(session, actor, event, UPDATED, fields, overrides=reached)
    return Edited(event, fields, dropped, reached)


async def add_override(
    session: AsyncSession,
    actor: Actor,
    series: CalendarEvent,
    wall: datetime,
    change: Change,
    times: Checked,
) -> CalendarEvent:
    """Stores a new override of the occurrence `wall` with the checked `times`."""
    content = {name: getattr(series, name) for name in CONTENT_FIELDS} | change.content()
    row = CalendarEvent(
        org_id=series.org_id,
        calendar_id=series.calendar_id,
        space_id=series.space_id,
        uid=series.uid,
        series_id=series.id,
        recurrence_id=wall,
        organizer_type=series.organizer_type,
        organizer_id=series.organizer_id,
        version=1,
        **content,
    )
    store_times(row, times)
    try:
        await EventRepository(session, series.org_id).add(row)
    except UidTaken:
        raise overridden() from None
    for hook in ON_OVERRIDE:
        await hook(session, series, row)
    await announce(session, actor, row, CREATED)
    return row


def overridden() -> Conflict:
    return Conflict("The occurrence has an override", code="event.occurrence_overridden")


async def override(
    session: AsyncSession,
    actor: Actor,
    series: CalendarEvent,
    wall: datetime,
    change: Change,
    *,
    dry_run: bool,
) -> Edited:
    """`scope=this`: a new override for the occurrence `wall` of `series`."""
    if change.names_series():
        raise invalid("event.scope_invalid")
    repo = EventRepository(session, series.org_id)
    if await repo.override_at(series.id, wall) is not None:
        raise overridden()
    zone = await repo.calendar_zone(series.calendar_id)
    checked = check(overlay(occurrence_times(stored_series(series), wall), change.values), zone)
    if dry_run:
        return Edited(series, [], wrote=False)
    row = await add_override(session, actor, series, wall, change, checked)
    return Edited(row, stored_names(change.values))


async def delete_one(
    session: AsyncSession, actor: Actor, series: CalendarEvent, wall: datetime
) -> Edited:
    """Deletes the occurrence `wall` of `series`: an EXDATE, and its override (if any)
    a tombstone; the series too when no occurrence is left."""
    if len(set(series.exdates) | {wall}) > DATES_MAX:
        raise invalid("event.too_many_dates")
    found = await EventRepository(session, series.org_id).override_at(series.id, wall)
    reached = (found,) if found is not None else ()
    series.exdates = sorted({*series.exdates, wall})
    if first_live(stored_series(series)) is None:
        return Edited(
            series, ["exdates"], reached=await end_series(session, actor, series, reached)
        )
    if found is not None:
        tombstone(found)
    series.recurs_until = until_of(series)
    series.version += 1
    await session.flush()
    await announce(session, actor, series, UPDATED, ["exdates"], overrides=reached)
    return Edited(series, ["exdates"], reached=reached)
