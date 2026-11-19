"""Events (plan M10 decisions 3 and 5): made in a calendar, read by id.

- Making one needs `calendar.write` in the calendar's space; a calendar the caller may
  not see answers 404 `calendar.not_found` (as for an unknown id). Its times are
  checked first (`event_times.check`, 422 with the problem's code); its organiser is
  the caller; its zone, unless named, the calendar's. One live master per UID and
  calendar (409 `event.uid_taken`).
- Reading one by id is the named way (decision 3): its organiser sees it whatever its
  space; anyone else through `access.require(calendar.read)` on its space, which an
  admin outside it passes audited (spec 5.5). How much: `sight.of`. An event the
  caller may not see answers 404 `event.not_found`, by the same statement as an
  unknown id (`EventRepository.find`).
- Every change writes one outbox event with ids only (`calendar_event.created`).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.access import Action, Actor, require, visible_space_ids
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.outbox import emit
from app.modules.calendars import sight
from app.modules.calendars.event_models import CalendarEvent, EventStatus, EventVisibility
from app.modules.calendars.event_repository import EventRepository, UidTaken
from app.modules.calendars.event_times import Times, check
from app.modules.calendars.repository import CalendarRepository
from app.modules.calendars.service import calendar_not_found
from app.modules.calendars.sight import Sight

UID_DOMAIN = "to-herd-cats-ai"
CREATED = "calendar_event.created"


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
class Seen:
    event: CalendarEvent
    sight: Sight


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
            uid=new.uid or f"{uuid7()}@{UID_DOMAIN}",
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
        await emit(
            self.session,
            type=CREATED,
            actor=actor,
            space_id=event.space_id,
            subject_type="calendar_event",
            subject_id=event.id,
            payload={"calendar_id": str(event.calendar_id)},
        )
        return event

    async def get(self, actor: Actor, event_id: uuid.UUID) -> Seen:
        """The event and how much of it the actor sees (404 `event.not_found` for
        none)."""
        repo = EventRepository(self.session, actor.org_id)
        seen = or_(CalendarEvent.space_id.in_(visible_space_ids(actor)), sight.attends_sql(actor))
        event = await repo.find(event_id, seen)
        if event is None:
            raise event_not_found()
        if sight.attends(actor, event):
            return Seen(event, Sight.FULL)
        try:
            await require(self.session, actor, Action.CALENDAR_READ, event.space_id)
        except (NotFound, Forbidden):
            raise event_not_found() from None
        found = sight.of(actor, event, reads=True, attends=False, named=True)
        if found is Sight.NONE:
            raise event_not_found()
        return Seen(event, found)
