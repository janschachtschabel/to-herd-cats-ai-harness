"""What a write of an event does to its invitations (plan M10 decision 7).

- A new override starts with a copy of its series' attendees and answers, the part a
  split makes takes them along (`copy_attendees` on the hooks `series.ON_OVERRIDE`
  and `series_split.CARRY`, registered when this module is imported: `events.py`,
  the one way into every change of an event, imports it).
- A change of the time of the row a write shows (`moved`) puts every other attendee's
  answer back to `needs_action` (who made the change keeps hers; agents stay
  accepted) and tells the people invited; so does cancelling it, or deleting it (the
  row named becomes a tombstone), without touching the answers. With `scope=all`
  the time changed when a stored time column did; with `this` and `following` when
  the change names other times than the named occurrence's, or a rule of its own.
  Only the row the write names or makes is told about (a series' attendees once, not
  once per override).
- Telling is an outbox event per person (`calendar_event.invited`, ids only: the
  calendar's and the person's); the handler writes the notification
  (`notifications.py`) and live delivery sends `event.invited` to that person.
  An answer is `calendar_event.responded` (the calendar's id and the answer's code).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.outbox import NewEvent, emit, emit_many
from app.modules.calendars import series, series_split
from app.modules.calendars.attendee_models import Response
from app.modules.calendars.attendee_repository import AttendeeRepository
from app.modules.calendars.event_change import occurrence
from app.modules.calendars.event_models import CalendarEvent, EventStatus
from app.modules.calendars.event_times import Times, check, overlay
from app.modules.calendars.event_writes import Change, Scope
from app.modules.calendars.series import Edited
from app.modules.calendars.series_rebase import occurrence_times, stored_series

INVITED = "calendar_event.invited"
RESPONDED = "calendar_event.responded"
# The stored columns whose change moves an event in time (EXDATEs only take some away).
TIME_COLUMNS = frozenset({"all_day", "starts_at", "ends_at", "tzid", "rrule", "rdates"})
RULE_FIELDS = ("rrule", "rdates")


async def copy_attendees(
    session: AsyncSession, source: CalendarEvent, target: CalendarEvent
) -> None:
    """`series.ON_OVERRIDE` and `series_split.CARRY`: `source`'s attendees and their
    answers onto the new row `target`."""
    await AttendeeRepository(session, source.org_id).copy(source.id, target.id)


def named_times(event: CalendarEvent, scope: Scope, named: str | None) -> Times | None:
    """Before a write with `scope=this`/`following` on a series: the times of the
    occurrence it names, as they are (None for any other write)."""
    if scope is Scope.ALL or event.series_id is not None or not event.recurring:
        return None
    return occurrence_times(stored_series(event), occurrence(event, named))


def moved(natural: Times | None, change: Change, edited: Edited, zone: str) -> bool:
    """Whether the write changed the time of the row it shows (`named_times` before)."""
    if natural is None:
        return bool(TIME_COLUMNS & set(edited.fields))
    if any(name in change.values for name in RULE_FIELDS):
        return True
    before, after = check(natural, zone), check(overlay(natural, change.values), zone)
    return (before.starts_at, before.ends_at, before.series.all_day) != (
        after.starts_at,
        after.ends_at,
        after.series.all_day,
    )


async def after_change(
    session: AsyncSession, actor: Actor, event: CalendarEvent, *, moved: bool, was: EventStatus
) -> None:
    """After a write that shows `event` (whose status was `was`): answers reset and
    the people told when it moved; told when it was cancelled by the write."""
    cancelled = event.status == EventStatus.CANCELLED and was != EventStatus.CANCELLED
    if not (moved or cancelled):
        return
    repo = AttendeeRepository(session, event.org_id)
    if moved:
        await repo.reset(event.id, actor.principal)
    await invited(session, actor, event, await repo.people(event.id))


async def after_delete(session: AsyncSession, actor: Actor, event: CalendarEvent) -> None:
    """After deleting: the people invited to the row named are told if it went."""
    if event.deleted_at is not None:
        people = await AttendeeRepository(session, event.org_id).people(event.id)
        await invited(session, actor, event, people)


async def invited(
    session: AsyncSession, actor: Actor, event: CalendarEvent, people: Iterable[uuid.UUID]
) -> None:
    """One `calendar_event.invited` per person (never the actor herself)."""
    payload = {"calendar_id": str(event.calendar_id)}
    events = [
        NewEvent(
            INVITED, event.space_id, "calendar_event", event.id, {**payload, "user_id": str(u)}
        )
        for u in dict.fromkeys(people)
        if u != actor.principal.id
    ]
    await emit_many(session, actor=actor, events=events)


async def responded(
    session: AsyncSession, actor: Actor, event: CalendarEvent, response: Response
) -> None:
    await emit(
        session,
        type=RESPONDED,
        actor=actor,
        space_id=event.space_id,
        subject_type="calendar_event",
        subject_id=event.id,
        payload={"calendar_id": str(event.calendar_id), "response": response.value},
    )


def _register() -> None:
    for hooks in (series.ON_OVERRIDE, series_split.CARRY):
        if copy_attendees not in hooks:
            hooks.append(copy_attendees)


_register()
