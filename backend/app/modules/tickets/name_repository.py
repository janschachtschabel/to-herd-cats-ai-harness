"""The names a ticket timeline entry shows for the ids it was written with (status
names, parent keys), for the message views. Called for messages of a ticket thread the
reader may see: the status and the parent are of the same ticket's space."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.models import TicketStatus, WorkItem


class TicketNameRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def status_names(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
        """The names of these statuses (one deleted since has none)."""
        wanted = list(set(ids))
        if not wanted:
            return {}
        stmt = select(TicketStatus.id, TicketStatus.name).where(
            TicketStatus.org_id == self.org_id, TicketStatus.id.in_(wanted)
        )
        return {row.id: row.name for row in await self.session.execute(stmt)}

    async def numbers(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
        """The numbers of these tickets."""
        wanted = list(set(ids))
        if not wanted:
            return {}
        stmt = select(WorkItem.id, WorkItem.number).where(
            WorkItem.org_id == self.org_id, WorkItem.id.in_(wanted)
        )
        return {row.id: row.number for row in await self.session.execute(stmt)}
