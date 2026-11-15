"""The SQL of "Neu beginnen" (`fresh_start.py`): the DM's row held against a person's
new message, and the cut from the database's clock (module review M8 4, K4)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.run_models import Run
from app.modules.messaging.models import Conversation, Message


class FreshStartRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock(self, conversation_id: uuid.UUID) -> Conversation | None:
        """The conversation as committed now, held `FOR NO KEY UPDATE` until the
        transaction ends: a person's new message there (`FOR SHARE`, with the run it
        queues) commits before it or waits for it; an agent's answer, whose foreign
        key takes only `FOR KEY SHARE`, does not wait."""
        stmt = (
            select(Conversation)
            .where(Conversation.org_id == self.org_id, Conversation.id == conversation_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def cut(self, conversation_id: uuid.UUID) -> datetime:
        """The database's clock now, but no earlier than anything the conversation
        holds (its messages, its runs' creation and start), whatever clock wrote them:
        all of that is before the cut."""
        messages = select(func.max(Message.created_at)).where(
            Message.org_id == self.org_id, Message.conversation_id == conversation_id
        )
        runs = select(func.max(func.greatest(Run.created_at, Run.started_at))).where(
            Run.org_id == self.org_id, Run.conversation_id == conversation_id
        )
        stmt = select(
            func.greatest(
                func.clock_timestamp(), messages.scalar_subquery(), runs.scalar_subquery()
            )
        )
        cut: datetime | None = await self.session.scalar(stmt)
        assert cut is not None
        return cut
