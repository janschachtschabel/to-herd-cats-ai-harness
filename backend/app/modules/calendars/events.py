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
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require, visible_space_ids
from app.core.errors import Conflict, Forbidden, NotFound
from app.modules.audit.recorder import record_private_event_reads
from app.modules.calendars import series, series_split, sight
from app.modules.calendars.event_models import CalendarEvent, EventStatus, EventVisibility
from app.modules.calendars.event_repository import EventRepository, UidTaken
from app.modules.calendars.event_times import Times, check, invalid
from app.modules.calendars.event_writes import (
    CREATED,
    DELETED,
    Change,
    Scope,
    announce,
    audit_admin_write,
    new_uid,
    refusals_roll_back,
    require_version,
    require_writable,
    tombstone,
)
from app.modules.calendars.repository import CalendarRepository
from app.modules.calendars.series_rebase import stored_series
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


def event_not_found() -> NotFound:
    return NotFound(code="event.not_found")


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
        event = await repo.find(event_id, sight.by_id_sql(actor))
        if event is None:
            raise event_not_found()
        return await self._named(actor, event)

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
        seen = await self._for_write(actor, event_id)
        event = seen.event
        async with refusals_roll_back(self.session):
            unhides = change.values.get("visibility", event.visibility) != event.visibility
            await require_writable(self.session, actor, seen, changes_visibility=unhides)
            require_version(event, version)
            edited = await self._edit(actor, event, change, scope, occurrence, dry_run)
            if not dry_run:
                await audit_admin_write(
                    self.session, actor, seen, change="update", scope=scope, fields=edited.fields
                )
        target = edited.event
        attends = sight.attends(actor, target)
        shown = sight.of(actor, target, reads=True, attends=attends, named=True)
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
        seen = await self._for_write(actor, event_id)
        event = seen.event
        async with refusals_roll_back(self.session):
            await require_writable(self.session, actor, seen)
            require_version(event, version)
            await self._remove(actor, event, scope, occurrence)
            await audit_admin_write(
                self.session, actor, seen, change="delete", scope=scope, fields=()
            )

    async def _edit(
        self,
        actor: Actor,
        event: CalendarEvent,
        change: Change,
        scope: Scope,
        occurrence: str | None,
        dry_run: bool,
    ) -> series.Edited:
        if scope is Scope.ALL:
            if event.series_id is not None and change.names_series():
                raise invalid("event.scope_invalid")  # an override is no series
            return await series.change_all(self.session, actor, event, change, dry_run=dry_run)
        wall = self._occurrence(event, occurrence)
        if scope is Scope.THIS:
            return await series.override(self.session, actor, event, wall, change, dry_run=dry_run)
        if wall == stored_series(event).start:  # splitting at the first: all
            return await series.change_all(self.session, actor, event, change, dry_run=dry_run)
        return await series_split.split(self.session, actor, event, wall, change, dry_run=dry_run)

    async def _remove(
        self, actor: Actor, event: CalendarEvent, scope: Scope, occurrence: str | None
    ) -> None:
        repo = EventRepository(self.session, actor.org_id)
        if event.series_id is not None and event.recurrence_id is not None:
            if scope is not Scope.ALL:
                raise invalid("event.scope_invalid")
            master = await repo.lock(event.series_id)
            if master is None:  # cannot be: the series' tombstone takes its overrides
                raise event_not_found()
            # Deleting an override deletes its occurrence (an EXDATE; it a tombstone).
            await series.delete_one(self.session, actor, master, event.recurrence_id)
            return
        if scope is not Scope.ALL:
            wall = self._occurrence(event, occurrence)
            if scope is Scope.THIS:
                await series.delete_one(self.session, actor, event, wall)
                return
            if wall != stored_series(event).start:
                await series_split.truncate(self.session, actor, event, wall)
                return
        for override in await repo.overrides_of(event.id):
            tombstone(override)
        tombstone(event)
        await self.session.flush()
        await announce(self.session, actor, event, DELETED)

    @staticmethod
    def _occurrence(event: CalendarEvent, occurrence: str | None) -> datetime:
        """The named occurrence of a series; `this` and `following` need a series."""
        if not event.recurring or event.series_id is not None:
            raise invalid("event.scope_invalid")
        return series.occurrence_of(event, occurrence)

    async def _for_write(self, actor: Actor, event_id: uuid.UUID) -> Seen:
        """The event as the named way sees it, locked (a series before its override)
        and read afresh."""
        repo = EventRepository(self.session, actor.org_id)
        event = await repo.find(event_id, sight.by_id_sql(actor))
        if event is None:
            raise event_not_found()
        seen = await self._named(actor, event)
        if event.series_id is not None:
            await repo.lock(event.series_id)
        locked = await repo.lock(event_id)
        if locked is None:  # deleted meanwhile
            raise event_not_found()
        return Seen(locked, seen.sight)

    async def _named(self, actor: Actor, event: CalendarEvent) -> Seen:
        """How much of the event found by id the actor sees; audited when admin power
        alone shows its content."""
        if sight.attends(actor, event):
            return Seen(event, Sight.FULL)
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
