"""What tickets give messaging (`messaging/ticket_hooks.py`, review M4 P9): a ticket
thread's ticket number for search and activity, the names on timeline entries, and
the people a comment in a ticket thread notifies. Registered by the package's
`__init__`, so importing anything of tickets makes it available."""

import uuid

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.principal import PrincipalType
from app.modules.messaging.models import Conversation
from app.modules.messaging.ticket_hooks import register_ticket_hooks
from app.modules.tickets.models import WorkItem, ticket_key
from app.modules.tickets.name_repository import TicketNameRepository


class _Hooks:
    def number(
        self, work_item_id: InstrumentedAttribute[uuid.UUID | None]
    ) -> ColumnElement[int | None]:
        return select(WorkItem.number).where(WorkItem.id == work_item_id).scalar_subquery()

    def key(self, number: int) -> str:
        return ticket_key(number)

    def names(
        self, session: AsyncSession, org_id: uuid.UUID, space_ids: Select[uuid.UUID]
    ) -> TicketNameRepository:
        return TicketNameRepository(session, org_id, space_ids)

    async def people(
        self, session: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> set[uuid.UUID]:
        stmt = (
            select(
                WorkItem.assignee_type,
                WorkItem.assignee_id,
                WorkItem.reporter_type,
                WorkItem.reporter_id,
            )
            .join(Conversation, Conversation.work_item_id == WorkItem.id)
            .where(Conversation.org_id == org_id, Conversation.id == conversation_id)
        )
        row = (await session.execute(stmt)).first()
        if row is None:
            return set()
        pairs = ((row[0], row[1]), (row[2], row[3]))
        return {pid for ptype, pid in pairs if ptype == PrincipalType.USER and pid is not None}


def register() -> None:
    register_ticket_hooks(_Hooks())
