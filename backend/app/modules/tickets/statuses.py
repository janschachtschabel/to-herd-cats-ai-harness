"""The status workflow of a space (spec 10, plan M4 decision 4).

Reading needs `ticket.read` in the space; creating, changing, reordering and deleting
statuses need `space.manage`. A status of a space the actor cannot read is 404
`ticket_status.not_found`, like an unknown id.

Rules, checked under the space's status lock (`StatusRepository.lock_space`):
- at most MAX_STATUSES per space; names unique in the space, ignoring case (409);
- the space always keeps a status of category `open` and one of category `done`
  (409 `ticket_status.category_required`), so no change makes one without;
- a status with tickets is deleted only with `replace_with`, another status of the
  same space, which takes its tickets (each gets a new version and a
  `ticket.updated` event);
- positions stay 0, 1, 2 … in order: a status put somewhere moves the others along.
Every change is audited in its transaction.
"""

import builtins
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require, space_ids_with
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, decode_score_cursor, encode_score_cursor
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.messaging.thread_repository import TicketThreadRepository
from app.modules.tickets.events import TICKET_UPDATED, Field, ticket_event
from app.modules.tickets.models import (
    MAX_STATUSES,
    REQUIRED_CATEGORIES,
    StatusCategory,
    TicketStatus,
)
from app.modules.tickets.status_repository import StatusRepository, StatusScope


def status_not_found() -> NotFound:
    return NotFound(code="ticket_status.not_found")


def status_repository(session: AsyncSession, actor: Actor) -> StatusRepository:
    """The actor's view of the statuses: the spaces where it may read tickets."""
    scope = StatusScope(actor.org_id, space_ids_with(actor, Action.TICKET_READ))
    return StatusRepository(session, scope)


class StatusService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[TicketStatus]:
        await require(self.session, actor, Action.TICKET_READ, space_id)
        after = None
        if params.cursor:
            position, id_ = decode_score_cursor(params.cursor)
            if not 0 <= position <= MAX_STATUSES:
                raise ValidationFailed("Invalid cursor", code="validation_failed")
            after = (int(position), id_)
        rows = await status_repository(self.session, actor).page(space_id, after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_score_cursor(items[-1].position, items[-1].id) if more else None
        return pagination.Page[TicketStatus](items=items, next_cursor=cursor)

    async def create(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        name: str,
        category: StatusCategory,
        position: int | None = None,
    ) -> TicketStatus:
        await require(self.session, actor, Action.SPACE_MANAGE, space_id)
        repo = status_repository(self.session, actor)
        await repo.lock_space(space_id)
        existing = await repo.in_space(space_id)
        if len(existing) >= MAX_STATUSES:
            raise Conflict(f"At most {MAX_STATUSES} statuses", code="ticket_status.too_many")
        if await repo.name_taken(space_id, name):
            raise Conflict(code="ticket_status.name_taken")
        status = await repo.add(
            TicketStatus(
                org_id=actor.org_id,
                space_id=space_id,
                name=name,
                category=category,
                position=len(existing),
            )
        )
        if position is not None:
            await repo.renumber(_placed(existing, status, position))
        await self._audit(actor, "ticket_status.created", status, {"name": name})
        return status

    async def update(
        self,
        actor: Actor,
        status_id: uuid.UUID,
        version: int,
        *,
        name: str | None = None,
        category: StatusCategory | None = None,
        position: int | None = None,
    ) -> TicketStatus:
        repo, status = await self._managed(actor, status_id)
        existing = await repo.in_space(status.space_id)
        _check_version(status, version)
        before = snapshot(status, ("name", "category", "position"))
        if name is not None and name != status.name:
            if await repo.name_taken(status.space_id, name, besides=status.id):
                raise Conflict(code="ticket_status.name_taken")
            status.name = name
        if category is not None and category != status.category:
            others = [s for s in existing if s.id != status.id]
            _require_categories([*(s.category for s in others), category])
            status.category = category
        if position is not None and position != status.position:
            others = [s for s in existing if s.id != status.id]
            await repo.renumber(_placed(others, status, position))
        if changed := changes(before, status):
            status.version += 1
            await self.session.flush()
            await self._audit(actor, "ticket_status.updated", status, {"changes": changed})
        return status

    async def delete(
        self,
        actor: Actor,
        status_id: uuid.UUID,
        version: int,
        replace_with: uuid.UUID | None = None,
    ) -> builtins.list[tuple[uuid.UUID, uuid.UUID]]:
        """Delete the status; its tickets go to `replace_with`. The tickets moved, as
        (ticket id, space id)."""
        repo, status = await self._managed(actor, status_id)
        existing = await repo.in_space(status.space_id)
        _check_version(status, version)
        others = [s for s in existing if s.id != status.id]
        _require_categories(s.category for s in others)
        moved: builtins.list[tuple[uuid.UUID, uuid.UUID]] = []
        if replace_with is not None:
            target = next((s for s in others if s.id == replace_with), None)
            if target is None:
                raise ValidationFailed(code="ticket_status.replacement_invalid")
            moved = await repo.move_tickets(status.id, target.id)
        elif await repo.in_use(status.id):
            raise Conflict("Name a status for its tickets", code="ticket_status.in_use")
        details: dict[str, Any] = {"name": status.name, "moved": len(moved)}
        if replace_with is not None:
            details["replaced_with"] = str(replace_with)
        await repo.delete(status)
        await repo.renumber(others)
        await self._audit(actor, "ticket_status.deleted", status, details)
        threads = await TicketThreadRepository(self.session, actor.org_id).thread_ids(
            [ticket_id for ticket_id, _ in moved]
        )
        for ticket_id, space_id in moved:  # each moved ticket changed: one event each
            await ticket_event(
                self.session,
                actor,
                TICKET_UPDATED,
                ticket_id=ticket_id,
                space_id=space_id,
                conversation_id=threads.get(ticket_id),
                changes={Field.STATUS: (status.id, replace_with)},
            )
        return moved

    async def _managed(
        self, actor: Actor, status_id: uuid.UUID
    ) -> tuple[StatusRepository, TicketStatus]:
        """The status, locked for a change by someone with `space.manage` in its space,
        after the space's status lock."""
        repo = status_repository(self.session, actor)
        status = await repo.get(status_id)
        if status is None:
            raise status_not_found()
        try:
            await require(self.session, actor, Action.SPACE_MANAGE, status.space_id)
        except NotFound:
            raise status_not_found() from None
        await repo.lock_space(status.space_id)
        status = await repo.get(status_id, lock=True)
        if status is None:  # deleted meanwhile
            raise status_not_found()
        return repo, status

    async def _audit(
        self, actor: Actor, action: str, status: TicketStatus, details: dict[str, Any]
    ) -> None:
        details = {"space_id": str(status.space_id), **details}
        await record(self.session, actor, action, "ticket_status", status.id, details)


def _check_version(status: TicketStatus, version: int) -> None:
    if status.version != version:
        raise Conflict(
            code="ticket_status.version_conflict", details={"current_version": status.version}
        )


def _placed(others: list[TicketStatus], status: TicketStatus, position: int) -> list[TicketStatus]:
    """`others` in order with `status` put at `position` (or last)."""
    ordered = [s for s in others if s.id != status.id]
    ordered.insert(min(position, len(ordered)), status)
    return ordered


def _require_categories(categories: Iterable[StatusCategory]) -> None:
    """The space keeps one status of each required category."""
    present = set(categories)
    if any(category not in present for category in REQUIRED_CATEGORIES):
        raise Conflict(
            "A space keeps an open and a done status", code="ticket_status.category_required"
        )
