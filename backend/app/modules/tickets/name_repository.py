"""The names a ticket timeline entry shows for the ids it was written with (status
names, parent keys), for the message views: only of the spaces where the reader may
read tickets (`space_ids`), so an id of anything else is never named (review M4 P1)."""

import uuid
from collections.abc import Iterable

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.models import TicketStatus, WorkItem


class TicketNameRepository:
    def __init__(
        self, session: AsyncSession, org_id: uuid.UUID, space_ids: Select[uuid.UUID]
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.space_ids = space_ids

    async def status_names(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
        """The names of these statuses (one deleted since, or hidden, has none)."""
        wanted = list(set(ids))
        if not wanted:
            return {}
        stmt = select(TicketStatus.id, TicketStatus.name).where(
            TicketStatus.org_id == self.org_id,
            TicketStatus.id.in_(wanted),
            TicketStatus.space_id.in_(self.space_ids),
        )
        return {row.id: row.name for row in await self.session.execute(stmt)}

    async def numbers(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
        """The numbers of these tickets (one hidden has none)."""
        wanted = list(set(ids))
        if not wanted:
            return {}
        stmt = select(WorkItem.id, WorkItem.number).where(
            WorkItem.org_id == self.org_id,
            WorkItem.id.in_(wanted),
            WorkItem.space_id.in_(self.space_ids),
        )
        return {row.id: row.number for row in await self.session.execute(stmt)}
