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
from app.core.access import Action, Actor, require
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams
from app.core.principal import Principal
from app.modules.audit.recorder import record
from app.modules.messaging.models import Conversation
from app.modules.tickets import hierarchy, listing
from app.modules.tickets.assignment import check_assignment
from app.modules.tickets.base import (
    editable,
    emit_change,
    leaves_closed_sprint,
    readable,
    ticket_not_found,
    ticket_repository,
    view_of,
    with_tags,
)
from app.modules.tickets.events import TICKET_CREATED, TICKET_UPDATED, Changes, Field
from app.modules.tickets.models import (
    Priority,
    Sprint,
    StatusCategory,
    TicketKind,
    TicketStatus,
    WorkItem,
)
from app.modules.tickets.repository import TicketRepository, TicketView
from app.modules.tickets.sprints import check_sprint, hold_for_move
from app.modules.tickets.statuses import status_repository
from app.modules.tickets.thread_repository import TicketThreadRepository

__all__ = ["TicketService", "ticket_not_found", "ticket_repository"]


def status_invalid() -> ValidationFailed:
    return ValidationFailed("Not a status of the ticket's space", code="ticket.status_invalid")


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
        await emit_change(self.session, actor, TICKET_CREATED, ticket, changes)
        await self._audit(actor, "ticket.created", ticket, {"number": ticket.number})
        await self._audit_changes(actor, ticket, changes, status)
        return await view_of(self.session, actor, repo, ticket.id)

    async def get(self, actor: Actor, number: int) -> TicketView:
        repo = ticket_repository(self.session, actor)
        ticket = await readable(self.session, actor, repo, number)
        return await view_of(self.session, actor, repo, ticket.id)

    async def thread_of(self, actor: Actor, number: int) -> Conversation:
        """The thread of the ticket `number`, for whoever sees the ticket (404
        `ticket.not_found` for anyone else)."""
        ticket = await readable(self.session, actor, ticket_repository(self.session, actor), number)
        return await self.thread(actor, ticket)

    async def thread(self, actor: Actor, ticket: WorkItem) -> Conversation:
        """The ticket's thread (spec 6.2), made with the ticket; for a ticket the actor
        has read."""
        return await TicketThreadRepository(self.session, actor.org_id).thread_for(ticket)

    async def children(self, actor: Actor, view: TicketView) -> dict[StatusCategory, int]:
        """For a ticket the actor has read."""
        return await ticket_repository(self.session, actor).children_counts(view.ticket.id)

    async def update(
        self, actor: Actor, number: int, version: int, values: dict[str, Any]
    ) -> TicketView:
        """`values`: the fields the client sent (`TicketUpdate`), null ones included."""
        parent_id = values.get("parent_id")
        held: dict[uuid.UUID, Sprint] = {}
        if "sprint_id" in values:
            held = await hold_for_move(self.session, actor, number, values["sprint_id"])
        repo, ticket = await editable(self.session, actor, number, version, parent_id=parent_id)
        changes = await self._changes(actor, repo, ticket, values, held)
        status = None
        if Field.STATUS in changes:
            status = await self._status(actor, ticket.space_id, values["status_id"])
            if Field.SPRINT not in changes and await leaves_closed_sprint(
                self.session, actor, ticket.sprint_id, status.category
            ):
                values = {**values, "sprint_id": None}
                changes = {**changes, Field.SPRINT: (ticket.sprint_id, None)}
        if not changes:
            return await view_of(self.session, actor, repo, ticket.id)
        _apply(ticket, values, changes)
        ticket.version += 1
        await self.session.flush()
        await emit_change(self.session, actor, TICKET_UPDATED, ticket, changes)
        await self._audit_changes(actor, ticket, changes, status)
        return await view_of(self.session, actor, repo, ticket.id)

    async def list(
        self, actor: Actor, filters: listing.Filters, sort: listing.Sort, params: PageParams
    ) -> pagination.Page[TicketView]:
        after = listing.decode(sort, params.cursor) if params.cursor else None
        repo = ticket_repository(self.session, actor)
        rows = await repo.page(filters, sort, after, params.limit + 1)
        items = await with_tags(self.session, actor, rows[: params.limit])
        more = len(rows) > params.limit
        cursor = None
        if more:
            last = items[-1].ticket
            value = listing.sort_value(sort, last.updated_at, last.due_on, last.priority)
            cursor = listing.encode(sort, listing.Position(value, last.number))
        return pagination.Page[TicketView](items=items, next_cursor=cursor)

    # --- helpers -------------------------------------------------------------------

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
        self,
        actor: Actor,
        repo: TicketRepository,
        ticket: WorkItem,
        values: dict[str, Any],
        sprints: dict[uuid.UUID, Sprint],
    ) -> Changes:
        """What the request changes, after checking the hierarchy, the assignment and the
        sprint (`sprints`: those held for the change)."""
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
        if "sprint_id" in values and values["sprint_id"] != ticket.sprint_id:
            if values["sprint_id"] is not None:
                check_sprint(sprints, ticket.space_id, values["sprint_id"])
            changes[Field.SPRINT] = (ticket.sprint_id, values["sprint_id"])
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
    for name in (
        "title",
        "description_md",
        "kind",
        "status_id",
        "priority",
        "due_on",
        "parent_id",
        "sprint_id",
    ):
        if name in values:
            setattr(ticket, name, values[name])
    if Field.ASSIGNEE in changes:
        new = values["assignee"]
        ticket.assignee_type = new.type if new else None
        ticket.assignee_id = new.id if new else None
