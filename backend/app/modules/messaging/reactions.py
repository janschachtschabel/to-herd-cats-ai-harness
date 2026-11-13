"""Reactions (spec 6.1): whoever may post in the conversation reacts with one emoji
(`emoji.is_emoji`; anything else is 422 `reaction.invalid_emoji`). Adding and
removing are idempotent; only a change is emitted (`reaction.changed`, ids only).
A deleted message takes no new reactions (409 `message.deleted`)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Conflict, ValidationFailed
from app.core.outbox import emit
from app.modules.messaging.emoji import is_emoji
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.service import MessageService
from app.modules.messaging.social_repository import ReactionRepository, ReactionSummary


class ReactionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.messages = MessageService(session)

    async def react(self, actor: Actor, message_id: uuid.UUID, emoji: str) -> list[ReactionSummary]:
        """The message's reactions, the actor's `emoji` among them."""
        message, conversation = await self._target(actor, message_id, emoji)
        if message.deleted_at is not None:
            raise Conflict(code="message.deleted")
        repo = ReactionRepository(self.session, actor.org_id)
        if await repo.add(message.id, actor.principal.id, emoji):
            await self._changed(actor, conversation, message)
        return await self._summary(actor, message)

    async def unreact(
        self, actor: Actor, message_id: uuid.UUID, emoji: str
    ) -> list[ReactionSummary]:
        """The message's reactions without the actor's `emoji`."""
        message, conversation = await self._target(actor, message_id, emoji)
        repo = ReactionRepository(self.session, actor.org_id)
        if await repo.remove(message.id, actor.principal.id, emoji):
            await self._changed(actor, conversation, message)
        return await self._summary(actor, message)

    async def _target(
        self, actor: Actor, message_id: uuid.UUID, emoji: str
    ) -> tuple[Message, Conversation]:
        if not is_emoji(emoji):
            raise ValidationFailed("exactly one emoji", code="reaction.invalid_emoji")
        message, conversation = await self.messages.readable(actor, message_id)
        await self.messages.reader.require_post(actor, conversation)
        return message, conversation

    async def _summary(self, actor: Actor, message: Message) -> list[ReactionSummary]:
        repo = ReactionRepository(self.session, actor.org_id)
        return (await repo.summaries([message.id], actor.principal.id)).get(message.id, [])

    async def _changed(self, actor: Actor, conversation: Conversation, message: Message) -> None:
        await emit(
            self.session,
            type="reaction.changed",
            actor=actor,
            space_id=conversation.space_id,
            subject_type="message",
            subject_id=message.id,
            payload={"conversation_id": str(conversation.id), "message_id": str(message.id)},
        )
