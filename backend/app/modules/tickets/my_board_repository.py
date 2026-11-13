"""The SQL of my board (plan M4b decision 4). Scoped like every ticket view (the
actor's organisation and the spaces where it may read tickets, `TicketRepository`):
the person's tickets of those spaces only, by status category; done ones only since
`done_since`, cancelled ones never. Each call is a fixed number of statements, however
many spaces and tickets: counts (one), the first page of every column (one), a page of
one column (one), the names of the spaces shown (one)."""

import uuid
from collections import defaultdict
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, literal, or_, select, tuple_

from app.core.principal import PrincipalType
from app.modules.spaces.models import Space
from app.modules.tickets.models import StatusCategory, TicketStatus, WorkItem
from app.modules.tickets.repository import TicketView
from app.modules.tickets.view_repository import BOARD_KEY, BoardPosition, ViewRepository

# My board's columns, in order.
CATEGORIES = (
    StatusCategory.OPEN,
    StatusCategory.ACTIVE,
    StatusCategory.REVIEW,
    StatusCategory.DONE,
)


class MyBoardRepository(ViewRepository):
    def _mine(self, user_id: uuid.UUID, done_since: datetime) -> ColumnElement[bool]:
        """The person's visible tickets on the board (over `work_item` joined with its
        status)."""
        return and_(
            self._visible(),
            WorkItem.assignee_type == PrincipalType.USER,
            WorkItem.assignee_id == user_id,
            TicketStatus.category.in_(CATEGORIES),
            or_(
                TicketStatus.category != StatusCategory.DONE,
                WorkItem.status_changed_at >= done_since,
            ),
        )

    async def my_counts(
        self, user_id: uuid.UUID, done_since: datetime
    ) -> dict[StatusCategory, int]:
        stmt = (
            select(TicketStatus.category, func.count())
            .select_from(WorkItem)
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .where(self._mine(user_id, done_since))
            .group_by(TicketStatus.category)
        )
        return {StatusCategory(c): int(n) for c, n in await self.session.execute(stmt)}

    async def my_first_pages(
        self, user_id: uuid.UUID, done_since: datetime, limit: int
    ) -> dict[StatusCategory, list[TicketView]]:
        """Up to `limit` tickets of every column, in board order, in one statement."""
        rank = func.row_number().over(partition_by=TicketStatus.category, order_by=BOARD_KEY)
        ranked = (
            select(WorkItem.id, rank.label("rank"))
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .where(self._mine(user_id, done_since))
            .subquery()
        )
        top = select(ranked.c.id).where(ranked.c.rank <= limit)
        stmt = self._views().where(WorkItem.id.in_(top)).order_by(*BOARD_KEY)
        columns: dict[StatusCategory, list[TicketView]] = defaultdict(list)
        for row in await self.session.execute(stmt):
            view = self._view(row)
            columns[StatusCategory(view.status.category)].append(view)
        return columns

    async def my_column(
        self,
        user_id: uuid.UUID,
        done_since: datetime,
        category: StatusCategory,
        after: BoardPosition | None,
        limit: int,
    ) -> list[TicketView]:
        stmt = self._views().where(
            self._mine(user_id, done_since), TicketStatus.category == category
        )
        if after is not None:
            stmt = stmt.where(
                tuple_(*BOARD_KEY)
                > tuple_(literal(after.rank), literal(after.due), literal(after.number))
            )
        rows = await self.session.execute(stmt.order_by(*BOARD_KEY).limit(limit))
        return [self._view(row) for row in rows]

    async def space_names(self, space_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
        """The names of these spaces (those of tickets the actor has read)."""
        if not space_ids:
            return {}
        stmt = select(Space.id, Space.name).where(
            Space.org_id == self.scope.org_id, Space.id.in_(space_ids)
        )
        return {row[0]: row[1] for row in await self.session.execute(stmt)}
