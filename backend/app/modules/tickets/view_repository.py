"""The SQL of the ticket views (plan M4 task 5): board, epic overview, counts. Scoped
like `TicketRepository` (the actor's organisation, the spaces where it may read
tickets), with the list's filters; each view is a fixed number of statements, however
many tickets and statuses there are (no query per column or per epic).

Board order (decision 8): priority descending, due date ascending (none last),
number ascending; a position in it is (`-rank`, due date, number), compared as one.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, func, literal, select, tuple_

from app.core.principal import PrincipalType
from app.modules.tickets.listing import LAST_DAY, Filters
from app.modules.tickets.models import (
    Priority,
    StatusCategory,
    TicketKind,
    TicketStatus,
    WorkItem,
)
from app.modules.tickets.repository import PRIORITY_RANK, TicketRepository, TicketView

OPEN_CATEGORIES = (StatusCategory.OPEN, StatusCategory.ACTIVE, StatusCategory.REVIEW)
_DUE = func.coalesce(WorkItem.due_on, LAST_DAY)
BOARD_KEY = (-PRIORITY_RANK, _DUE, WorkItem.number)


@dataclass(frozen=True, slots=True)
class BoardPosition:
    """Where a column's page ended: its last ticket's place in the board order."""

    rank: int  # minus the priority's rank
    due: date
    number: int


def board_position(view: TicketView) -> BoardPosition:
    ticket = view.ticket
    return BoardPosition(-Priority(ticket.priority).rank, ticket.due_on or LAST_DAY, ticket.number)


class ViewRepository(TicketRepository):
    def _in_space(self, space_id: uuid.UUID) -> ColumnElement[bool]:
        return WorkItem.space_id == space_id

    async def column_counts(self, space_id: uuid.UUID, filters: Filters) -> dict[uuid.UUID, int]:
        """How many tickets each status of the space holds, under the filters."""
        stmt = (
            select(WorkItem.status_id, func.count())
            .where(self._visible(), self._in_space(space_id))
            .group_by(WorkItem.status_id)
        )
        stmt = self._filtered(stmt, filters)
        return {status_id: int(n) for status_id, n in await self.session.execute(stmt)}

    async def first_pages(
        self, space_id: uuid.UUID, filters: Filters, limit: int
    ) -> dict[uuid.UUID, list[TicketView]]:
        """Up to `limit` tickets of every status of the space, in board order, in one
        statement (a rank within each status)."""
        rank = func.row_number().over(partition_by=WorkItem.status_id, order_by=BOARD_KEY)
        ranked = select(WorkItem.id, rank.label("rank")).where(
            self._visible(), self._in_space(space_id)
        )
        inner = self._filtered(ranked, filters).subquery()
        top = select(inner.c.id).where(inner.c.rank <= limit)
        stmt = self._views().where(WorkItem.id.in_(top)).order_by(*BOARD_KEY)
        columns: dict[uuid.UUID, list[TicketView]] = defaultdict(list)
        for row in await self.session.execute(stmt):
            view = self._view(row)
            columns[view.ticket.status_id].append(view)
        return columns

    async def column(
        self,
        space_id: uuid.UUID,
        status_id: uuid.UUID,
        filters: Filters,
        after: BoardPosition | None,
        limit: int,
    ) -> list[TicketView]:
        """A page of one status's tickets, in board order, after `after`."""
        stmt = self._views().where(self._in_space(space_id), WorkItem.status_id == status_id)
        stmt = self._filtered(stmt, filters)
        if after is not None:
            stmt = stmt.where(
                tuple_(*BOARD_KEY)
                > tuple_(literal(after.rank), literal(after.due), literal(after.number))
            )
        rows = await self.session.execute(stmt.order_by(*BOARD_KEY).limit(limit))
        return [self._view(row) for row in rows]

    async def epics(
        self, space_id: uuid.UUID, before_number: int | None, limit: int
    ) -> list[TicketView]:
        """The space's epics, newest first."""
        stmt = self._views().where(self._in_space(space_id), WorkItem.kind == TicketKind.EPIC)
        if before_number is not None:
            stmt = stmt.where(WorkItem.number < before_number)
        rows = await self.session.execute(stmt.order_by(WorkItem.number.desc()).limit(limit))
        return [self._view(row) for row in rows]

    async def children_of(
        self, ticket_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[StatusCategory, int]]:
        """How many children each ticket has, per category, in one statement (tickets
        the actor has read: their children live in their space)."""
        found: dict[uuid.UUID, dict[StatusCategory, int]] = defaultdict(dict)
        if not ticket_ids:
            return found
        stmt = (
            select(WorkItem.parent_id, TicketStatus.category, func.count())
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .where(WorkItem.org_id == self.scope.org_id, WorkItem.parent_id.in_(ticket_ids))
            .group_by(WorkItem.parent_id, TicketStatus.category)
        )
        for parent_id, category, n in await self.session.execute(stmt):
            if parent_id is not None:
                found[parent_id][StatusCategory(category)] = int(n)
        return found

    async def assigned_open(self, user_id: uuid.UUID) -> int:
        """The person's tickets not done or cancelled, in the spaces the actor sees."""
        stmt = (
            select(func.count())
            .select_from(WorkItem)
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .where(
                self._visible(),
                WorkItem.assignee_type == PrincipalType.USER,
                WorkItem.assignee_id == user_id,
                TicketStatus.category.in_(OPEN_CATEGORIES),
            )
        )
        return int(await self.session.scalar(stmt) or 0)
