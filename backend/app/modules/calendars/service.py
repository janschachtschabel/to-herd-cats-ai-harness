"""Calendars per space (plan M10 decisions 2 and 3).

Rights only from `core/access.py`: reading needs `calendar.read` in the calendar's
space, making, renaming, recolouring and archiving `calendar.moderate`. A calendar the
caller may not see, an archived one and an unknown id all answer 404
`calendar.not_found`, at the same cost (`CalendarRepository.find`: one statement).

The lists hold for admins as for anyone (C1): `list` shows the calendars of the spaces
the person belongs to (`access.member_space_ids`); another space's calendars an admin
reaches only by naming the space (`list_in`, `readable`), which goes through
`access.require` and is audited for team and personal spaces (spec 5.5).

At most `MAX_CALENDARS_PER_SPACE` calendars that are not archived per space (409
`calendar.limit`), counted under the space's row lock. Every change names the version
it read (409 `calendar.version_conflict`). A default calendar cannot be archived (409
`calendar.default_kept`).

Known gap (review M10 task 1, R1-M2; shared with tickets and sprints): `require`
writes an admin's `admin.access` in the request's transaction, so a refused change
(409) rolls it back with the request. No helper writes audit outside that
transaction; events (task 3b) must audit before anything that can refuse.
"""

import builtins
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, member_space_ids, require, visible_space_ids
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.models_base import utcnow
from app.core.pagination import PageParams, decode_id_cursor
from app.modules.calendars import zones
from app.modules.calendars.defaults import ensure_default, ensure_defaults, wants_default
from app.modules.calendars.models import (
    DEFAULT_TIME_ZONE,
    MAX_CALENDARS_PER_SPACE,
    Calendar,
    CalendarColor,
)
from app.modules.calendars.repository import CalendarRepository

EDITABLE = ("name", "color", "time_zone")


@dataclass(frozen=True, slots=True)
class NewCalendar:
    name: str
    color: CalendarColor = CalendarColor.BLUE
    time_zone: str = DEFAULT_TIME_ZONE


def calendar_not_found() -> NotFound:
    return NotFound(code="calendar.not_found")


def _check_zone(time_zone: str) -> None:
    try:
        zones.zone(time_zone)
    except zones.ZoneUnknown:
        raise ValidationFailed(code="calendar.invalid_time_zone") from None


class CalendarService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _repo(self, actor: Actor) -> CalendarRepository:
        return CalendarRepository(self.session, actor.org_id)

    async def list(self, actor: Actor, params: PageParams) -> pagination.Page[Calendar]:
        """The calendars of the spaces the actor belongs to (never by admin power)."""
        await ensure_defaults(self.session, actor)
        return await self._page(actor, member_space_ids(actor), params)

    async def list_in(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[Calendar]:
        """The space's calendars, for whoever may read them there (the named way:
        an admin's look into a foreign team or personal space is audited)."""
        await require(self.session, actor, Action.CALENDAR_READ, space_id)
        await ensure_defaults(self.session, actor, only=space_id)
        return await self._page(actor, [space_id], params)

    async def readable(self, actor: Actor, calendar_id: uuid.UUID) -> Calendar:
        """A calendar the actor may read (404 `calendar.not_found` otherwise); an
        admin outside the space reaches it through `require`, audited."""
        calendar = await self._repo(actor).find(calendar_id, visible_space_ids(actor))
        if calendar is None:
            raise calendar_not_found()
        try:
            await require(self.session, actor, Action.CALENDAR_READ, calendar.space_id)
        except NotFound:
            raise calendar_not_found() from None
        return calendar

    async def create(self, actor: Actor, space_id: uuid.UUID, new: NewCalendar) -> Calendar:
        await require(self.session, actor, Action.CALENDAR_MODERATE, space_id)
        _check_zone(new.time_zone)
        repo = self._repo(actor)
        space = await repo.lock_space(space_id)
        if space is None:  # gone since the check
            raise NotFound(code="space.not_found")
        if wants_default(space):  # the default comes first and counts
            await ensure_default(self.session, actor, space_id)
        if await repo.count_active(space_id) >= MAX_CALENDARS_PER_SPACE:
            raise Conflict(
                f"At most {MAX_CALENDARS_PER_SPACE} calendars per space",
                code="calendar.limit",
            )
        return await repo.add(
            Calendar(
                org_id=actor.org_id,
                space_id=space_id,
                name=new.name,
                color=new.color,
                time_zone=new.time_zone,
            )
        )

    async def update(
        self, actor: Actor, calendar_id: uuid.UUID, version: int, values: dict[str, Any]
    ) -> Calendar:
        """`values`: the fields the client sent (none of them null)."""
        calendar = await self._managed(actor, calendar_id, version)
        if "time_zone" in values:
            _check_zone(values["time_zone"])
        changed = [n for n in EDITABLE if n in values and values[n] != getattr(calendar, n)]
        if not changed:
            return calendar
        for name in changed:
            setattr(calendar, name, values[name])
        calendar.version += 1
        await self.session.flush()
        return calendar

    async def archive(self, actor: Actor, calendar_id: uuid.UUID, version: int) -> None:
        """Gone for everyone: out of every list, 404 by id; its rows stay. A default
        calendar is kept (409 `calendar.default_kept`): it is made once and there is no
        way back from archiving."""
        calendar = await self._managed(actor, calendar_id, version)
        if calendar.is_default:
            raise Conflict("A default calendar is kept", code="calendar.default_kept")
        calendar.archived_at = utcnow()
        calendar.version += 1
        await self.session.flush()

    async def _managed(self, actor: Actor, calendar_id: uuid.UUID, version: int) -> Calendar:
        """The calendar, locked for a change by someone with `calendar.moderate` in
        its space, at the version the client read."""
        repo = self._repo(actor)
        calendar = await repo.find(calendar_id, visible_space_ids(actor))
        if calendar is None:
            raise calendar_not_found()
        try:
            await require(self.session, actor, Action.CALENDAR_MODERATE, calendar.space_id)
        except NotFound:
            raise calendar_not_found() from None
        locked = await repo.find(calendar_id, visible_space_ids(actor), lock=True)
        if locked is None:  # archived meanwhile
            raise calendar_not_found()
        if locked.version != version:
            raise Conflict(
                code="calendar.version_conflict", details={"current_version": locked.version}
            )
        return locked

    async def _page(
        self,
        actor: Actor,
        space_ids: Select[uuid.UUID] | builtins.list[uuid.UUID],
        params: PageParams,
    ) -> pagination.Page[Calendar]:
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows: builtins.list[Calendar] = await self._repo(actor).page(
            space_ids, after, params.limit + 1
        )
        return pagination.id_page(rows, params.limit, lambda c: c.id)
