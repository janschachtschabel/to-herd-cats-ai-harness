"""The SQL of the daily view (plan M4b decision 5): a space's board grouped by
assignee. Scoped like every ticket view (`ViewRepository`), with the board's filters;
two statements however many people, statuses and tickets: the counts per person and
status (with how many changed status since a moment), and the first tickets of every
cell of the people shown."""

import uuid
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.principal import PrincipalType
from app.modules.tickets.listing import Filters
from app.modules.tickets.models import WorkItem
from app.modules.tickets.repository import TicketView
from app.modules.tickets.view_repository import BOARD_KEY, ViewRepository
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class Group:
    """The tickets of one person (None: nobody) in one status."""

    assignee_id: uuid.UUID | None
    assignee_name: str | None
    status_id: uuid.UUID
    count: int
    changed: int  # how many changed status since the moment asked about


class DailyRepository(ViewRepository):
    async def groups(self, space_id: uuid.UUID, filters: Filters, since: datetime) -> list[Group]:
        """Every (person, status) of the space's tickets under the filters."""
        changed = func.count().filter(WorkItem.status_changed_at >= since)
        stmt = (
            select(WorkItem.assignee_id, User.name, WorkItem.status_id, func.count(), changed)
            .outerjoin(
                User,
                and_(
                    WorkItem.assignee_type == PrincipalType.USER,
                    User.id == WorkItem.assignee_id,
                    User.org_id == WorkItem.org_id,
                ),
            )
            .where(self._visible(), self._in_space(space_id))
            .group_by(WorkItem.assignee_id, User.name, WorkItem.status_id)
        )
        stmt = self._filtered(stmt, filters)
        return [
            Group(row[0], row[1], row[2], int(row[3]), int(row[4]))
            for row in await self.session.execute(stmt)
        ]

    async def cells(
        self,
        space_id: uuid.UUID,
        filters: Filters,
        people: Collection[uuid.UUID],
        unassigned: bool,
        limit: int,
    ) -> dict[tuple[uuid.UUID | None, uuid.UUID], list[TicketView]]:
        """Up to `limit` tickets of every (person, status) of `people` (and of nobody,
        with `unassigned`), in board order, in one statement."""
        rank = func.row_number().over(
            partition_by=(WorkItem.assignee_id, WorkItem.status_id), order_by=BOARD_KEY
        )
        whose = [WorkItem.assignee_id.in_(list(people))] if people else []
        if unassigned:
            whose.append(WorkItem.assignee_id.is_(None))
        found: dict[tuple[uuid.UUID | None, uuid.UUID], list[TicketView]] = defaultdict(list)
        if not whose:
            return found
        ranked = select(WorkItem.id, rank.label("rank")).where(
            self._visible(), self._in_space(space_id), or_(*whose)
        )
        inner = self._filtered(ranked, filters).subquery()
        top = select(inner.c.id).where(inner.c.rank <= limit)
        stmt = self._views().where(WorkItem.id.in_(top)).order_by(*BOARD_KEY)
        for row in await self.session.execute(stmt):
            view = self._view(row)
            found[(view.ticket.assignee_id, view.ticket.status_id)].append(view)
        return found
