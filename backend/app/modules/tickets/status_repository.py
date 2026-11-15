"""The SQL of ticket statuses. Scoped by the actor's organisation and the spaces where
it may read tickets (`StatusScope`): a status of a space the actor cannot see is never
loaded. Changes to a space's statuses are serialised (`lock_space`), so the count, the
name and the required categories hold under concurrent requests.

Locks against tickets moving in while a status is deleted (review focus 4): a ticket
write takes its status `FOR NO KEY UPDATE` (`lock_for_use`, `first_of`:
`with_for_update(key_share=True)` renders that); a deletion takes the status `FOR
UPDATE` first (`get(lock=True)`), so either the ticket's write commits before the
deletion moves the status's tickets, or it finds the status gone. The lock also keeps
the status from changing its category while a ticket takes it; ticket writes into the
same status wait for each other for the length of their short transactions.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.tickets.models import StatusCategory, TicketStatus, WorkItem


@dataclass(frozen=True, slots=True)
class StatusScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces where the actor may read tickets (SQL)


class StatusRepository:
    def __init__(self, session: AsyncSession, scope: StatusScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        return and_(
            TicketStatus.org_id == self.scope.org_id,
            TicketStatus.space_id.in_(self.scope.space_ids),
        )

    async def lock_space(self, space_id: uuid.UUID) -> None:
        """Serialise changes to the space's statuses until the transaction ends."""
        await advisory_xact_lock(self.session, f"ticket.statuses:{space_id}")

    async def add(self, status: TicketStatus) -> TicketStatus:
        self.session.add(status)
        await self.session.flush()
        return status

    async def get(self, status_id: uuid.UUID, *, lock: bool = False) -> TicketStatus | None:
        """The status if the actor may see it; with `lock`, as committed now and locked
        (`FOR UPDATE`) until the transaction ends."""
        stmt = (
            select(TicketStatus)
            .where(self._visible(), TicketStatus.id == status_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def lock_for_use(self, space_id: uuid.UUID, status_id: uuid.UUID) -> TicketStatus | None:
        """The space's status `status_id`, held (`FOR NO KEY UPDATE`) so it cannot be
        deleted or change its category before the ticket that takes it commits; None if
        the space has no such status."""
        stmt = (
            select(TicketStatus)
            .where(
                TicketStatus.org_id == self.scope.org_id,
                TicketStatus.space_id == space_id,
                TicketStatus.id == status_id,
            )
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def first_of(self, space_id: uuid.UUID, category: StatusCategory) -> TicketStatus | None:
        """The space's first status (by position) of the category, held like
        `lock_for_use`."""
        stmt = (
            select(TicketStatus)
            .where(
                TicketStatus.org_id == self.scope.org_id,
                TicketStatus.space_id == space_id,
                TicketStatus.category == category,
            )
            .order_by(TicketStatus.position, TicketStatus.id)
            .limit(1)
            .with_for_update(key_share=True)
        )
        return await self.session.scalar(stmt)

    async def in_space(self, space_id: uuid.UUID) -> list[TicketStatus]:
        """Every status of the space, in order (at most MAX_STATUSES)."""
        stmt = (
            select(TicketStatus)
            .where(TicketStatus.org_id == self.scope.org_id, TicketStatus.space_id == space_id)
            .order_by(TicketStatus.position, TicketStatus.id)
            .execution_options(populate_existing=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def page(
        self, space_id: uuid.UUID, after: tuple[int, uuid.UUID] | None, limit: int
    ) -> list[TicketStatus]:
        """The space's statuses in order; `after` is the (position, id) of the last row
        of the page before."""
        stmt = (
            select(TicketStatus)
            .where(self._visible(), TicketStatus.space_id == space_id)
            .order_by(TicketStatus.position, TicketStatus.id)
            .limit(limit)
        )
        if after is not None:
            position, id_ = after
            stmt = stmt.where(
                or_(
                    TicketStatus.position > position,
                    and_(TicketStatus.position == position, TicketStatus.id > id_),
                )
            )
        return list((await self.session.scalars(stmt)).all())

    async def name_taken(
        self, space_id: uuid.UUID, name: str, *, besides: uuid.UUID | None = None
    ) -> bool:
        clauses = [
            TicketStatus.space_id == space_id,
            func.lower(TicketStatus.name) == name.lower(),
        ]
        if besides is not None:
            clauses.append(TicketStatus.id != besides)
        return bool(await self.session.scalar(select(exists().where(*clauses))))

    async def renumber(self, ordered: Sequence[TicketStatus]) -> None:
        """Positions 0, 1, 2 … in the given order."""
        for position, status in enumerate(ordered):
            if status.position != position:
                status.position = position
        await self.session.flush()

    async def in_use(self, status_id: uuid.UUID) -> bool:
        stmt = select(exists().where(WorkItem.status_id == status_id))
        return bool(await self.session.scalar(stmt))

    async def move_tickets(
        self, from_id: uuid.UUID, to_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]]:
        """Every ticket of status `from_id` into `to_id` (a new version each, locked
        until the transaction ends); the (id, space_id, sprint_id) of each."""
        stmt = (
            update(WorkItem)
            .where(WorkItem.org_id == self.scope.org_id, WorkItem.status_id == from_id)
            .values(status_id=to_id, version=WorkItem.version + 1)
            .returning(WorkItem.id, WorkItem.space_id, WorkItem.sprint_id)
            .execution_options(synchronize_session=False)
        )
        return [(row[0], row[1], row[2]) for row in await self.session.execute(stmt)]

    async def delete(self, status: TicketStatus) -> None:
        await self.session.delete(status)
        await self.session.flush()
