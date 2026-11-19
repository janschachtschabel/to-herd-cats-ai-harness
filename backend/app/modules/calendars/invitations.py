"""Invitations and answers (plan M10 decision 7): rows on an event, read and set by id
on the named way (`events.EventService`).

- Setting an event's attendees is a write of the event: full sight and
  `calendar.write` in its space (`event_writes.require_writable`), at the version read
  (409), which it raises. New people and agents must be ones the inviter may name
  (with `directory.read` any active person; without it, a guest's case, only readers
  of the event's space; agents only with `ai.use`; 422 `event.attendee_unknown`, as
  for an id that names nobody). On a series the change (who comes, who goes) reaches
  its overrides too, which needs full sight of each (`series_reach`). New people are
  told (`invitation`); agents are accepted at once and start nothing.
- Reading the attendee list needs full sight of the event (403 `event.private`).
- Answering needs a row of one's own on the event row (403 `event.not_invited`) and
  names the event's version read (409 after any change, a time change above all); it
  leaves the version as it is. An answer on a series reaches each override whose
  answer of the person still followed the series'. The organiser hears of a decline
  or a "maybe" (`notifications.py`).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import Forbidden, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.calendars.attendee_lists import (
    Diff,
    Invitee,
    Kind,
    change_row,
    diff,
    key_of,
    new_row,
    too_many,
)
from app.modules.calendars.attendee_models import MAX_ATTENDEES, Response
from app.modules.calendars.attendee_repository import AttendeeRepository, Known, Listed
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from app.modules.calendars.event_writes import (
    UPDATED,
    Scope,
    announce,
    audit_admin_write,
    private,
    refusals_roll_back,
    require_version,
    require_writable,
)
from app.modules.calendars.events import EventService
from app.modules.calendars.invitation_effects import invited, responded
from app.modules.calendars.series_reach import require_full_sight
from app.modules.calendars.sight import Sight

ATTENDEES = "attendees"  # how `calendar_event.updated` and the audit name the change


class InvitationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_attendees(
        self, actor: Actor, event_id: uuid.UUID, wanted: Sequence[Invitee], *, version: int
    ) -> CalendarEvent:
        """The event's attendees become `wanted`; the event as stored."""
        seen = await EventService(self.session).for_write(actor, event_id)
        event = seen.event
        async with refusals_roll_back(self.session):
            await require_writable(self.session, actor, seen)
            require_version(event, version)
            repo = AttendeeRepository(self.session, actor.org_id)
            change = diff(await repo.of_event(event.id), wanted)
            await self._require_known(actor, event, change)
            overrides = await self._overrides(event)
            by_power = await require_full_sight(self.session, actor, overrides)
            await self._apply(event, change)
            for override in overrides:
                await self._apply(override, self._reaching(change), partial=True)
            event.version += 1
            await self.session.flush()
            await announce(self.session, actor, event, UPDATED, [ATTENDEES], overrides=overrides)
            people = [i.id for i in change.added if i.kind is Kind.USER and i.id is not None]
            await invited(self.session, actor, event, people)
            if not change.empty:
                await audit_admin_write(
                    self.session,
                    actor,
                    seen,
                    change="update",
                    scope=Scope.ALL,
                    fields=[ATTENDEES],
                    overrides_by_power=by_power,
                )
        return event

    async def attendees(
        self, actor: Actor, event_id: uuid.UUID, params: PageParams
    ) -> tuple[CalendarEvent, Page[Listed]]:
        """A page of the event's attendees (only with full sight of it)."""
        seen = await EventService(self.session).get(actor, event_id)
        if seen.sight is not Sight.FULL:
            raise private()
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await AttendeeRepository(self.session, actor.org_id).page(
            seen.event.id, after, params.limit + 1
        )
        return seen.event, id_page(rows, params.limit, lambda row: row.attendee.id)

    async def respond(
        self, actor: Actor, event_id: uuid.UUID, response: Response, *, version: int
    ) -> Listed:
        """The actor's answer to the event row; her attendee row as stored."""
        seen = await EventService(self.session).for_write(actor, event_id)
        event = seen.event
        repo = AttendeeRepository(self.session, actor.org_id)
        mine = await repo.mine(event.id, actor.principal)
        if mine is None:
            raise Forbidden(code="event.not_invited")
        require_version(event, version)
        old = Response(mine.response)
        mine.response = response
        await self.session.flush()
        if event.recurring and event.series_id is None and old != response:
            await repo.follow(event.id, actor.principal, old, response)
        await responded(self.session, actor, event, response)
        (listed,) = await repo.page(event.id, None, 1, only=mine.id)
        return listed

    async def _require_known(self, actor: Actor, event: CalendarEvent, change: Diff) -> None:
        named = {i.principal for i in change.added if i.principal is not None}
        if not named:
            return
        may = Known(
            everyone=await can(self.session, actor, Action.DIRECTORY_READ),
            agents=await can(self.session, actor, Action.AI_USE),
        )
        known = await AttendeeRepository(self.session, actor.org_id).known(
            named, space_id=event.space_id, viewer=actor.principal.id, may=may
        )
        if named - known:
            raise ValidationFailed("No such attendee", code="event.attendee_unknown")

    async def _overrides(self, event: CalendarEvent) -> list[CalendarEvent]:
        """The live overrides a series' attendee change reaches (locked)."""
        if event.series_id is not None or not event.recurring:
            return []
        return await EventRepository(self.session, event.org_id).overrides_of(event.id)

    @staticmethod
    def _reaching(change: Diff) -> Diff:
        """What of a series' change reaches an override: who comes and who goes."""
        return Diff(added=change.added, removed=change.removed)

    async def _apply(self, event: CalendarEvent, change: Diff, *, partial: bool = False) -> None:
        """Writes `change` onto the event row's attendees (an override's: by who the
        attendee is, adding only who is not there yet)."""
        repo = AttendeeRepository(self.session, event.org_id)
        current = await repo.of_event(event.id) if partial else []
        have = {key_of(attendee): attendee for attendee in current}
        gone = {key_of(attendee) for attendee in change.removed}
        removed = [a for key, a in have.items() if key in gone] if partial else change.removed
        added = [i for i in change.added if not partial or i.key not in have]
        if partial and len(have) - len(removed) + len(added) > MAX_ATTENDEES:
            raise too_many()
        await repo.remove(removed)
        for attendee, invitee in change.changed:
            change_row(attendee, invitee)
        await repo.add(new_row(event.org_id, event.id, invitee) for invitee in added)
