"""Events (plan M10 decisions 3 and 5): made in a calendar, read by id.

- Making one needs `calendar.write` in the calendar's space; a calendar the caller may
  not see answers 404 `calendar.not_found` (as for an unknown id). Its times are
  checked first (`event_times.check`, 422 with the problem's code); its organiser is
  the caller; its zone, unless named, the calendar's. One live master per UID and
  calendar (409 `event.uid_taken`).
- Reading one by id is the named way (decision 3): its organiser sees it whatever its
  space; anyone else through `access.require(calendar.read)` on its space, which an
  admin outside it passes audited (spec 5.5). How much: `sight.of`; content shown by
  admin power alone is audited (`calendar.private_read`). An event the
  caller may not see answers 404 `event.not_found`, by the same statement as an
  unknown id (`EventRepository.find`).
- Changing and deleting one (task 3b) is the named way too, under a row lock (a series
  before its override): full sight and `calendar.write` (`event_writes.require_writable`),
  the version read (409), then the scope (`series`, `series_split`). A refusal keeps
  the audit written before it (`event_writes.refusals_roll_back`); a write by admin
  power alone is audited. Deleting leaves a tombstone: the series with its overrides
  (`scope=all`), an EXDATE (`scope=this`, also for deleting an override), or the end
  of the series (`scope=following`; at the first occurrence: all).
- Every change writes one outbox event with ids only (`calendar_event.created`,
  `.updated` with the fields' names, `.deleted`).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require, visible_space_ids
from app.core.errors import Conflict, Forbidden, NotFound
from app.modules.audit.recorder import record_private_event_reads
from app.modules.calendars import sight
from app.modules.calendars.event_change import edit, event_not_found, lock_for_write, remove
from app.modules.calendars.event_models import CalendarEvent, EventStatus, EventVisibility
from app.modules.calendars.event_repository import EventRepository, UidTaken
from app.modules.calendars.event_times import Times, check
from app.modules.calendars.event_writes import (
    CREATED,
    Change,
    Scope,
    announce,
    audit_admin_write,
    new_uid,
    refusals_roll_back,
    require_version,
    require_writable,
)
from app.modules.calendars.invitation_effects import (
    after_change,
    after_delete,
    moved,
    named_times,
)
from app.modules.calendars.repository import CalendarRepository
from app.modules.calendars.series_reach import require_full_sight
from app.modules.calendars.service import calendar_not_found
from app.modules.calendars.sight import Seen, Sight


@dataclass(frozen=True, slots=True)
class NewEvent:
    title: str
    times: Times
    description: str = ""
    location: str = ""
    status: EventStatus = EventStatus.CONFIRMED
    visibility: EventVisibility = EventVisibility.DEFAULT
    busy: bool | None = None  # None: busy unless all-day (decision 3)
    uid: str | None = None  # None: one is made


@dataclass(frozen=True, slots=True)
class Changed:
    """What a change answers: the event it shows (the series, the new override or the
    new part of a split), how much of it the caller sees, and what it dropped."""

    event: CalendarEvent
    sight: Sight
    dropped_overrides: int
    dropped_exdates: int


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, actor: Actor, calendar_id: uuid.UUID, new: NewEvent) -> CalendarEvent:
        calendar = await CalendarRepository(self.session, actor.org_id).find(
            calendar_id, visible_space_ids(actor)
        )
        if calendar is None:
            raise calendar_not_found()
        try:
            await require(self.session, actor, Action.CALENDAR_WRITE, calendar.space_id)
        except NotFound:
            raise calendar_not_found() from None
        checked = check(new.times, calendar.time_zone)
        event = CalendarEvent(
            org_id=actor.org_id,
            calendar_id=calendar.id,
            space_id=calendar.space_id,
            uid=new.uid or new_uid(),
            title=new.title,
            description=new.description,
            location=new.location,
            all_day=new.times.all_day,
            starts_at=checked.starts_at,
            ends_at=checked.ends_at,
            tzid=checked.tzid,
            rrule=checked.rrule,
            rdates=list(checked.rdates),
            exdates=list(checked.exdates),
            recurs_until=checked.recurs_until,
            status=new.status,
            visibility=new.visibility,
            busy=(not new.times.all_day) if new.busy is None else new.busy,
            organizer_type=actor.principal.type,
            organizer_id=actor.principal.id,
            version=1,
        )
        try:
            await EventRepository(self.session, actor.org_id).add(event)
        except UidTaken:
            raise Conflict(
                "The calendar has an event with this UID", code="event.uid_taken"
            ) from None
        await announce(self.session, actor, event, CREATED)
        return event

    async def get(self, actor: Actor, event_id: uuid.UUID) -> Seen:
        """The event and how much of it the actor sees (404 `event.not_found` for
        none)."""
        repo = EventRepository(self.session, actor.org_id)
        found = await repo.find(event_id, sight.by_id_sql(actor), sight.attends_sql(actor))
        if found is None:
            raise event_not_found()
        return await self._named(actor, *found)

    async def update(
        self,
        actor: Actor,
        event_id: uuid.UUID,
        change: Change,
        *,
        scope: Scope,
        occurrence: str | None,
        version: int,
        dry_run: bool = False,
    ) -> Changed:
        seen = await self.for_write(actor, event_id)
        event = seen.event
        async with refusals_roll_back(self.session):
            unhides = change.values.get("visibility", event.visibility) != event.visibility
            await require_writable(self.session, actor, seen, changes_visibility=unhides)
            require_version(event, version)
            natural, was = named_times(event, scope, occurrence), EventStatus(event.status)
            edited = await edit(self.session, actor, event, change, scope, occurrence, dry_run)
            by_power = await require_full_sight(self.session, actor, edited.reached)
            if edited.wrote:
                zone = await EventRepository(self.session, actor.org_id).calendar_zone(
                    event.calendar_id
                )
                shifted = moved(natural, change, edited, zone)
                await after_change(
                    self.session, actor, edited.event, edited, moved=shifted, was=was
                )
                await audit_admin_write(
                    self.session,
                    actor,
                    seen,
                    change="update",
                    scope=scope,
                    fields=edited.fields,
                    overrides_by_power=by_power,
                )
        target = edited.event
        attended = await EventRepository(self.session, actor.org_id).attended(
            [target], sight.attends_sql(actor)
        )
        shown = sight.of(actor, target, reads=True, attends=target.id in attended, named=True)
        return Changed(target, shown, edited.dropped.overrides, edited.dropped.exdates)

    async def delete(
        self,
        actor: Actor,
        event_id: uuid.UUID,
        *,
        scope: Scope,
        occurrence: str | None,
        version: int,
    ) -> None:
        seen = await self.for_write(actor, event_id)
        event = seen.event
        async with refusals_roll_back(self.session):
            await require_writable(self.session, actor, seen)
            require_version(event, version)
            removed = await remove(self.session, actor, event, scope, occurrence)
            by_power = await require_full_sight(self.session, actor, removed.reached)
            await after_delete(self.session, actor, event, removed, scope)
            await audit_admin_write(
                self.session,
                actor,
                seen,
                change="delete",
                scope=scope,
                fields=(),
                overrides_by_power=by_power,
            )

    async def for_write(self, actor: Actor, event_id: uuid.UUID) -> Seen:
        """The event as the named way sees it, locked (a series before its override)
        and read afresh; how much of it the actor sees is judged on that row (review
        M10 task 3b, R3b-6), whether the actor attends it too. Every write of an event
        found by id starts here (its attendees and answers too: `invitations.py`)."""
        repo = EventRepository(self.session, actor.org_id)
        found = await repo.find(event_id, sight.by_id_sql(actor), sight.attends_sql(actor))
        if found is None:
            raise event_not_found()
        locked = await lock_for_write(self.session, found[0])
        attended = await repo.attended([locked], sight.attends_sql(actor))
        return await self._named(actor, locked, locked.id in attended)

    async def _named(self, actor: Actor, event: CalendarEvent, attends: bool) -> Seen:
        """How much of the event found by id the actor sees; audited when admin power
        alone shows its content."""
        if attends:
            return Seen(event, Sight.FULL, attends=True)
        try:
            await require(self.session, actor, Action.CALENDAR_READ, event.space_id)
        except (NotFound, Forbidden):
            raise event_not_found() from None
        found = sight.of(actor, event, reads=True, attends=False, named=True)
        if found is Sight.NONE:
            raise event_not_found()
        if sight.by_admin_power(actor, event, reads=True, attends=False, named=True):
            await record_private_event_reads(
                self.session, actor, [(event.id, event.space_id, event.calendar_id)]
            )
        return Seen(event, found)
