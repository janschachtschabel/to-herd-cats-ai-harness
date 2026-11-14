"""The SQL of sprints (plan M4b). Scoped like tickets (`TicketScope`: the actor's
organisation and the spaces where it may read tickets): a sprint of any other space is
never loaded, whether asked for by id, as a ticket's sprint or as the next sprint.

Locks (plan M4b review focus 2), always sprints before tickets; a closing takes the
sprint, then the space's status lock (`StatusRepository.lock_space`, which a status
deletion holds while it moves its tickets), then the sprint's tickets (`lock_tickets`):
sprint → space statuses → tickets.
- a sprint being changed, started or closed: `FOR NO KEY UPDATE` (`get(lock=True)`);
  it never changes its key, so the foreign key checks of tickets put into the next
  sprint (`FOR KEY SHARE`) do not wait for it;
- the sprints a ticket leaves and joins: `FOR SHARE`, in the order of their ids,
  before the ticket (`hold`). A sprint being closed waits for the tickets moving in
  or out of it to commit, and they wait for it, so the tickets a closing counts are
  exactly the tickets in the sprint when it closes.
"""

import uuid
from collections.abc import Collection, Sequence
from datetime import date

from sqlalchemy import (
    ColumnElement,
    Integer,
    and_,
    case,
    exists,
    literal,
    select,
    tuple_,
    type_coerce,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.modules.tickets.models import Sprint, SprintState, StatusCategory, TicketStatus, WorkItem
from app.modules.tickets.repository import TicketScope

# The list's order: active, planned (earliest start first), closed (latest end first),
# as one number per sprint (`order_key`), the id breaking ties.
_RANK = 100_000_000
_DAYS = 10_000_000
_EPOCH = date(2000, 1, 1)  # any day (not date.min: the driver sends it as -infinity)


def order_key(state: SprintState, starts_on: date, ends_on: date) -> int:
    if state == SprintState.ACTIVE:
        return starts_on.toordinal()
    if state == SprintState.PLANNED:
        return _RANK + starts_on.toordinal()
    return 2 * _RANK + _DAYS - ends_on.toordinal()


def _ordinal(column: InstrumentedAttribute[date]) -> ColumnElement[int]:
    """`date.toordinal` in SQL (a date minus a date is a number of days)."""
    days = type_coerce(column - literal(_EPOCH), Integer)
    return days + _EPOCH.toordinal()


_ORDER_KEY = case(
    (Sprint.state == SprintState.ACTIVE, _ordinal(Sprint.starts_on)),
    (Sprint.state == SprintState.PLANNED, _RANK + _ordinal(Sprint.starts_on)),
    else_=2 * _RANK + _DAYS - _ordinal(Sprint.ends_on),
)
FINISHED = (StatusCategory.DONE, StatusCategory.CANCELLED)


class SprintRepository:
    def __init__(self, session: AsyncSession, scope: TicketScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        return and_(Sprint.org_id == self.scope.org_id, Sprint.space_id.in_(self.scope.space_ids))

    async def add(self, sprint: Sprint) -> Sprint:
        self.session.add(sprint)
        await self.session.flush()
        return sprint

    async def get(self, sprint_id: uuid.UUID, *, lock: bool = False) -> Sprint | None:
        """The sprint if the actor may see it; with `lock`, as committed now and held
        (`FOR NO KEY UPDATE`) until the transaction ends."""
        stmt = (
            select(Sprint)
            .where(self._visible(), Sprint.id == sprint_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update(key_share=True)
        return await self.session.scalar(stmt)

    async def page(
        self,
        space_id: uuid.UUID,
        states: Collection[SprintState],
        after: tuple[int, uuid.UUID] | None,
        limit: int,
    ) -> list[Sprint]:
        stmt = select(Sprint).where(self._visible(), Sprint.space_id == space_id)
        if states:
            stmt = stmt.where(Sprint.state.in_(states))
        if after is not None:
            stmt = stmt.where(tuple_(_ORDER_KEY, Sprint.id) > tuple_(literal(after[0]), after[1]))
        stmt = stmt.order_by(_ORDER_KEY, Sprint.id).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def active_exists(self, space_id: uuid.UUID) -> bool:
        stmt = select(
            exists().where(
                Sprint.org_id == self.scope.org_id,
                Sprint.space_id == space_id,
                Sprint.state == SprintState.ACTIVE,
            )
        )
        return bool(await self.session.scalar(stmt))

    async def hold(
        self, space_id: uuid.UUID, ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, Sprint]:
        """The space's sprints among `ids`, held (`FOR SHARE`) in the order of their ids
        until the transaction ends."""
        if not ids:
            return {}
        stmt = (
            select(Sprint)
            .where(self._visible(), Sprint.space_id == space_id, Sprint.id.in_(ids))
            .order_by(Sprint.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return {sprint.id: sprint for sprint in await self.session.scalars(stmt)}

    async def next_planned(self, space_id: uuid.UUID) -> Sprint | None:
        """The space's planned sprint that starts first."""
        stmt = (
            select(Sprint)
            .where(
                self._visible(), Sprint.space_id == space_id, Sprint.state == SprintState.PLANNED
            )
            .order_by(Sprint.starts_on, Sprint.id)
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def lock_tickets(self, sprint_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """The tickets in the sprint as committed now, locked (`FOR UPDATE`) in the order
        of their ids: (id, status id) of each."""
        stmt = (
            select(WorkItem.id, WorkItem.status_id)
            .where(WorkItem.org_id == self.scope.org_id, WorkItem.sprint_id == sprint_id)
            .order_by(WorkItem.id)
            .with_for_update()
        )
        return [(row[0], row[1]) for row in await self.session.execute(stmt)]

    async def categories(self, status_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not status_ids:
            return {}
        stmt = select(TicketStatus.id, TicketStatus.category).where(
            TicketStatus.org_id == self.scope.org_id, TicketStatus.id.in_(status_ids)
        )
        return {row[0]: row[1] for row in await self.session.execute(stmt)}

    async def move_tickets(
        self, ticket_ids: Sequence[uuid.UUID], sprint_id: uuid.UUID | None
    ) -> None:
        """Tickets (locked by the caller) into the sprint, or out of any; a new version
        each."""
        if not ticket_ids:
            return
        stmt = (
            update(WorkItem)
            .where(WorkItem.org_id == self.scope.org_id, WorkItem.id.in_(ticket_ids))
            .values(sprint_id=sprint_id, version=WorkItem.version + 1)
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)
