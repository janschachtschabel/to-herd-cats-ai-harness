"""Changing a series (plan M10 decision 6, I4 and I6): the whole of it, one occurrence,
or one occurrence deleted. Splitting it is `series_split`.

- Occurrences are named by their wall time in the series' zone (`recurrence_id`, the
  window's `OccurrenceOut.recurrence_id`); `occurrence_of` takes one back (422
  `event.occurrence_required`/`event.occurrence_unknown`; a deleted one is unknown).
- `change_all` (`scope=all`) changes the row itself. A series' pieces move with its
  start and what no longer names an occurrence is dropped (`series_rebase.rebase`); the
  answer counts it (`Dropped`), and `dry_run` only counts.
- `override` (`scope=this`) adds an override: a row of its own with the series' UID,
  content and organiser, at the occurrence's time unless the change names another; it
  is no series (naming `rrule`, `rdates` or `exdates` is 422 `event.scope_invalid`).
  An occurrence with an override already answers 409 `event.occurrence_overridden`.
  Task 4 copies the series' attendees into it.
- `delete_one` (`scope=this` on delete, or deleting an override) adds an EXDATE (at most
  500, 422 `event.too_many_dates`) and makes the occurrence's override a tombstone.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import Conflict
from app.modules.calendars import recurrence
from app.modules.calendars.event_models import DATES_MAX, CalendarEvent
from app.modules.calendars.event_repository import EventRepository, UidTaken
from app.modules.calendars.event_times import TIME_FIELDS, check, invalid, overlay, times_of
from app.modules.calendars.event_writes import (
    CONTENT_FIELDS,
    CREATED,
    UPDATED,
    Change,
    announce,
    changed_fields,
    snapshot,
    tombstone,
)
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


@dataclass(frozen=True, slots=True)
class Edited:
    """What a change wrote: the event the answer shows, the stored fields it changed
    and what it dropped."""

    event: CalendarEvent
    fields: list[str]
    dropped: Dropped = Dropped()


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


async def change_all(
    session: AsyncSession, actor: Actor, event: CalendarEvent, change: Change, *, dry_run: bool
) -> Edited:
    """`scope=all`: the row itself (a series, a single event or an override)."""
    repo = EventRepository(session, event.org_id)
    rebased: Rebased | None = None
    if any(name in change.values for name in TIME_FIELDS):
        overrides = await repo.overrides_of(event.id) if event.series_id is None else []
        zone = await repo.calendar_zone(event.calendar_id)
        rebased = rebase(
            times_of(event), stored_series(event).start, change.values, overrides, zone
        )
    dropped = rebased.counts() if rebased else Dropped()
    if dry_run:
        return Edited(event, [], dropped)
    before = snapshot(event)
    for name, value in change.content().items():
        setattr(event, name, value)
    if rebased is not None:
        store_times(event, rebased.checked)
        await move_overrides(session, rebased)
    fields = changed_fields(before, event)
    if fields or (rebased and rebased.dropped):
        event.version += 1
        await session.flush()
        await announce(session, actor, event, UPDATED, fields)
    return Edited(event, fields, dropped)


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
    zone = await repo.calendar_zone(series.calendar_id)
    checked = check(overlay(occurrence_times(stored_series(series), wall), change.values), zone)
    if dry_run:
        return Edited(series, [])
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
    store_times(row, checked)
    try:
        await repo.add(row)
    except UidTaken:
        raise Conflict(
            "The occurrence has an override", code="event.occurrence_overridden"
        ) from None
    await announce(session, actor, row, CREATED)
    return Edited(row, sorted(change.values))


async def delete_one(
    session: AsyncSession, actor: Actor, series: CalendarEvent, wall: datetime
) -> Edited:
    """Deletes the occurrence `wall` of `series`: an EXDATE, and its override (if any)
    a tombstone."""
    if len(set(series.exdates) | {wall}) > DATES_MAX:
        raise invalid("event.too_many_dates")
    repo = EventRepository(session, series.org_id)
    for found in await repo.overrides_of(series.id, since=wall):
        if found.recurrence_id == wall:
            tombstone(found)
    series.exdates = sorted({*series.exdates, wall})
    series.recurs_until = until_of(series)
    series.version += 1
    await session.flush()
    await announce(session, actor, series, UPDATED, ["exdates"])
    return Edited(series, ["exdates"])
