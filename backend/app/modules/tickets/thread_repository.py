"""The SQL of ticket threads (`messaging/thread_repository.py` holds what all threads
share): for the ticket services (after the caller's check of the ticket) and the
timeline handler (no actor: the event's organisation)."""

import uuid

from sqlalchemy import and_, select

from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.thread_repository import ThreadRepository
from app.modules.tickets.models import WorkItem


class TicketThreadRepository(ThreadRepository):
    async def ticket_and_thread(self, ticket_id: uuid.UUID) -> tuple[WorkItem, Conversation] | None:
        """The ticket and its thread (inserted if it has none yet), in one statement
        when it has one; None if the ticket is gone."""
        stmt = (
            select(WorkItem, Conversation)
            .outerjoin(
                Conversation,
                and_(Conversation.org_id == self.org_id, Conversation.work_item_id == WorkItem.id),
            )
            .where(WorkItem.org_id == self.org_id, WorkItem.id == ticket_id)
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        ticket, thread = row
        return ticket, thread if thread is not None else await self.thread_for(ticket)

    async def thread_for(self, ticket: WorkItem) -> Conversation:
        """The ticket's thread, inserted if it has none yet."""
        values = {
            "kind": ConversationKind.THREAD_TICKET,
            "space_id": ticket.space_id,
            "work_item_id": ticket.id,
        }
        return await self._thread(values, "work_item_id")

    async def thread_ids(self, ticket_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        """The threads of these tickets (ticket id → conversation id)."""
        if not ticket_ids:
            return {}
        stmt = select(Conversation.work_item_id, Conversation.id).where(
            Conversation.org_id == self.org_id, Conversation.work_item_id.in_(ticket_ids)
        )
        return {row[0]: row[1] for row in await self.session.execute(stmt) if row[0]}
