"""Tickets (spec 10): create, read, change, assign, list.

Rights (plan M4 decision 3) come only from `core/access.py`: a ticket is seen by whoever
may read tickets in its space; anyone else gets 404 `ticket.not_found`, the same as
for a number nobody has. Creating needs `ticket.create`, any change `ticket.edit`;
assigning someone else, or taking a ticket from someone, also `ticket.assign`
(`assignment.py`). Every change names the version it read (409
`ticket.version_conflict`), is emitted as one event (`events.py`) and, where it
creates, assigns or cancels, audited, all in its transaction.
"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require, space_ids_with
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams
from app.core.principal import Principal
from app.modules.audit.recorder import record
from app.modules.tickets import hierarchy, listing
from app.modules.tickets.assignment import check_assignment
from app.modules.tickets.events import TICKET_CREATED, TICKET_UPDATED, Changes, Field, ticket_event
from app.modules.tickets.models import (
    Priority,
    StatusCategory,
    TicketKind,
    TicketStatus,
    WorkItem,
)
from app.modules.tickets.repository import TicketRepository, TicketScope, TicketView
from app.modules.tickets.statuses import status_repository


def ticket_not_found() -> NotFound:
    return NotFound(code="ticket.not_found")


def status_invalid() -> ValidationFailed:
    return ValidationFailed("Not a status of the ticket's space", code="ticket.status_invalid")


def ticket_repository(session: AsyncSession, actor: Actor) -> TicketRepository:
    """The actor's view of the tickets: the spaces where it may read them."""
    scope = TicketScope(actor.org_id, space_ids_with(actor, Action.TICKET_READ))
    return TicketRepository(session, scope)


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        *,
        title: str,
        description_md: str = "",
        kind: TicketKind = TicketKind.TASK,
        status_id: uuid.UUID | None = None,
        priority: Priority = Priority.NORMAL,
        due_on: date | None = None,
        parent_id: uuid.UUID | None = None,
        assignee: Principal | None = None,
    ) -> TicketView:
        await require(self.session, actor, Action.TICKET_CREATE, space_id)
        repo = ticket_repository(self.session, actor)
        status = await self._status(actor, space_id, status_id)
        if parent_id is not None:
            parent = await repo.parent_in(space_id, parent_id)
            if parent is None:
                raise hierarchy.parent_invalid()
            hierarchy.check_parent(kind, parent.kind)
        if assignee is not None:
            await check_assignment(self.session, actor, repo, space_id, None, assignee)
        ticket = await repo.add(
            WorkItem(
                org_id=actor.org_id,
                space_id=space_id,
                number=await repo.next_number(),
                kind=kind,
                parent_id=parent_id,
                title=title,
                description_md=description_md,
                status_id=status.id,
                priority=priority,
                assignee_type=assignee.type if assignee else None,
                assignee_id=assignee.id if assignee else None,
                reporter_type=actor.principal.type,
                reporter_id=actor.principal.id,
                due_on=due_on,
            )
        )
        changes: dict[Field, tuple[Any, Any]] = {}
        if assignee is not None:
            changes[Field.ASSIGNEE] = (None, assignee.id)
        await self._emit(actor, TICKET_CREATED, ticket, changes)
        await self._audit(actor, "ticket.created", ticket, {"number": ticket.number})
        await self._audit_changes(actor, ticket, changes, status)
        return await self._view(repo, ticket.id)

    async def get(self, actor: Actor, number: int) -> TicketView:
        repo = ticket_repository(self.session, actor)
        ticket = await self._readable(actor, repo, number)
        return await self._view(repo, ticket.id)

    async def children(self, actor: Actor, view: TicketView) -> dict[StatusCategory, int]:
        """For a ticket the actor has read."""
        return await ticket_repository(self.session, actor).children_counts(view.ticket.id)

    async def update(
        self, actor: Actor, number: int, version: int, values: dict[str, Any]
    ) -> TicketView:
        """`values`: the fields the client sent (`TicketUpdate`), null ones included."""
        repo = ticket_repository(self.session, actor)
        ticket = await self._readable(actor, repo, number, lock=True)
        await require(self.session, actor, Action.TICKET_EDIT, ticket.space_id)
        if ticket.version != version:
            raise Conflict(
                code="ticket.version_conflict", details={"current_version": ticket.version}
            )
        changes = await self._changes(actor, repo, ticket, values)
        status = None
        if Field.STATUS in changes:
            status = await self._status(actor, ticket.space_id, values["status_id"])
        if not changes:
            return await self._view(repo, ticket.id)
        _apply(ticket, values, changes)
        ticket.version += 1
        await self.session.flush()
        await self._emit(actor, TICKET_UPDATED, ticket, changes)
        await self._audit_changes(actor, ticket, changes, status)
        return await self._view(repo, ticket.id)

    async def list(
        self, actor: Actor, filters: listing.Filters, sort: listing.Sort, params: PageParams
    ) -> pagination.Page[TicketView]:
        after = listing.decode(sort, params.cursor) if params.cursor else None
        repo = ticket_repository(self.session, actor)
        rows = await repo.page(filters, sort, after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = None
        if more:
            last = items[-1].ticket
            value = listing.sort_value(sort, last.updated_at, last.due_on, last.priority)
            cursor = listing.encode(sort, listing.Position(value, last.number))
        return pagination.Page[TicketView](items=items, next_cursor=cursor)

    # --- helpers -------------------------------------------------------------------

    async def _readable(
        self, actor: Actor, repo: TicketRepository, number: int, *, lock: bool = False
    ) -> WorkItem:
        ticket = await repo.by_number(number, lock=lock)
        if ticket is None:
            raise ticket_not_found()
        try:  # also notes an admin's look into a team or personal space (spec 5.5)
            await require(self.session, actor, Action.TICKET_READ, ticket.space_id)
        except NotFound:
            raise ticket_not_found() from None
        return ticket

    async def _view(self, repo: TicketRepository, ticket_id: uuid.UUID) -> TicketView:
        view = await repo.view(ticket_id)
        if view is None:  # only if it went away after the check
            raise ticket_not_found()
        return view

    async def _status(
        self, actor: Actor, space_id: uuid.UUID, status_id: uuid.UUID | None
    ) -> TicketStatus:
        """The space's status `status_id` (or its first open one), held until commit."""
        statuses = status_repository(self.session, actor)
        if status_id is None:
            status = await statuses.first_of(space_id, StatusCategory.OPEN)
        else:
            status = await statuses.lock_for_use(space_id, status_id)
        if status is None:
            raise status_invalid()
        return status

    async def _changes(
        self, actor: Actor, repo: TicketRepository, ticket: WorkItem, values: dict[str, Any]
    ) -> Changes:
        """What the request changes, after checking the hierarchy and the assignment."""
        changes: dict[Field, tuple[Any, Any]] = {}
        simple = {
            "title": Field.TITLE,
            "description_md": Field.DESCRIPTION,
            "kind": Field.KIND,
            "status_id": Field.STATUS,
            "priority": Field.PRIORITY,
            "due_on": Field.DUE_ON,
            "parent_id": Field.PARENT,
        }
        for name, field in simple.items():
            if name in values and values[name] != getattr(ticket, name):
                changes[field] = (getattr(ticket, name), values[name])
        if "assignee" in values:
            new = values["assignee"]
            old = _assignee(ticket)
            if new != old:
                await check_assignment(self.session, actor, repo, ticket.space_id, old, new)
                changes[Field.ASSIGNEE] = (old.id if old else None, new.id if new else None)
        if Field.KIND in changes or Field.PARENT in changes:
            await self._check_hierarchy(repo, ticket, values, changes)
        return changes

    async def _check_hierarchy(
        self,
        repo: TicketRepository,
        ticket: WorkItem,
        values: dict[str, Any],
        changes: Changes,
    ) -> None:
        kind = TicketKind(values.get("kind") or ticket.kind)
        parent_id = values["parent_id"] if "parent_id" in values else ticket.parent_id
        if parent_id is not None:
            parent = (
                None if parent_id == ticket.id else await repo.parent_in(ticket.space_id, parent_id)
            )
            if parent is None:
                raise hierarchy.parent_invalid()
            hierarchy.check_parent(kind, parent.kind)
        if Field.KIND in changes:
            hierarchy.check_children(kind, await repo.child_kinds(ticket.id))

    async def _emit(self, actor: Actor, type_: str, ticket: WorkItem, changes: Changes) -> None:
        await ticket_event(
            self.session,
            actor,
            type_,
            ticket_id=ticket.id,
            space_id=ticket.space_id,
            conversation_id=None,
            changes=changes,
        )

    async def _audit_changes(
        self, actor: Actor, ticket: WorkItem, changes: Changes, status: TicketStatus | None
    ) -> None:
        """Assignments and cancellations go into the audit log."""
        if Field.ASSIGNEE in changes:
            old, new = changes[Field.ASSIGNEE]
            details = {"from": str(old) if old else None, "to": str(new) if new else None}
            await self._audit(actor, "ticket.assigned", ticket, details)
        if status is not None and status.category == StatusCategory.CANCELLED:
            await self._audit(actor, "ticket.cancelled", ticket, {"status_id": str(status.id)})

    async def _audit(
        self, actor: Actor, action: str, ticket: WorkItem, details: dict[str, Any]
    ) -> None:
        details = {"space_id": str(ticket.space_id), **details}
        await record(self.session, actor, action, "ticket", ticket.id, details)


def _assignee(ticket: WorkItem) -> Principal | None:
    if ticket.assignee_type is None or ticket.assignee_id is None:
        return None
    return Principal(ticket.assignee_type, ticket.assignee_id)


def _apply(ticket: WorkItem, values: dict[str, Any], changes: Changes) -> None:
    for name in ("title", "description_md", "kind", "status_id", "priority", "due_on", "parent_id"):
        if name in values:
            setattr(ticket, name, values[name])
    if Field.ASSIGNEE in changes:
        new = values["assignee"]
        ticket.assignee_type = new.type if new else None
        ticket.assignee_id = new.id if new else None
