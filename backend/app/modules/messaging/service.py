"""Conversations as a whole: reading one, and what the caller may do there."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.modules.messaging.models import Conversation
from app.modules.messaging.visibility import ConversationReader


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = ConversationReader(session)

    async def get(self, actor: Actor, conversation_id: uuid.UUID) -> Conversation:
        return await self.reader.readable(actor, conversation_id)

    async def can_post(self, actor: Actor, conversation: Conversation) -> bool:
        """For display; writes check again (`ConversationReader.require_post`)."""
        return await self.reader.can_post(actor, conversation)
