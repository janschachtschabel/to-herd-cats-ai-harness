"""Who sees and who writes in which conversation, for every messaging service.

Rights (spec 5.3) come only from `core/access.py`:
- A channel lives in a space; a space the actor cannot read hides its channels, which
  then answer 404 `conversation.not_found` like an unknown id (never 403). The
  repository is scoped by `visible_space_ids`, so such a row is never even loaded.
- Writing in a channel needs `channel.post` in its space (`viewer` and up), managing
  it `channel.manage` (`moderator` and up). Nobody writes in an archived channel
  (409 `conversation.archived`); reading stays possible.
- A page thread lives in its page's space and is seen by whoever sees the page
  (drafts only with `page.edit`, nothing while it is in the trash); writing in it
  needs `channel.post` there, as in a channel.
- A direct message belongs to no space: its participants see it and write in it
  (guests too), nobody else. It has nothing to manage.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require, space_ids_with, visible_space_ids
from app.core.errors import Conflict, NotFound
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.repository import ConversationRepository, ConversationScope


def conversation_not_found() -> NotFound:
    return NotFound(code="conversation.not_found")


def check_version(conversation: Conversation, version: int) -> None:
    if conversation.version != version:
        raise Conflict(
            code="conversation.version_conflict",
            details={"current_version": conversation.version},
        )


class ConversationReader:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def scope(self, actor: Actor) -> ConversationScope:
        return ConversationScope(
            actor.org_id,
            actor.principal,
            visible_space_ids(actor),
            space_ids_with(actor, Action.CHANNEL_POST),
            space_ids_with(actor, Action.PAGE_EDIT),
        )

    def repo(self, actor: Actor) -> ConversationRepository:
        """The actor's view of the conversations."""
        return ConversationRepository(self.session, self.scope(actor))

    async def readable(
        self, actor: Actor, conversation_id: uuid.UUID, *, lock: bool = False
    ) -> Conversation:
        """The conversation if the actor may see it, else 404; with `lock`, as
        committed now and locked until the transaction ends."""
        conversation = await self.repo(actor).visible(conversation_id, lock=lock)
        if conversation is None:
            raise conversation_not_found()
        if conversation.kind != ConversationKind.DM:  # a DM: seen means taking part
            await self.require_in_space(actor, Action.SPACE_READ, conversation)
        return conversation

    async def require_in_space(
        self, actor: Actor, action: Action, conversation: Conversation
    ) -> None:
        """`require` in the conversation's space, where a space gone from view hides
        the conversation. Also notes an admin's look into a team space (spec 5.5)."""
        if conversation.space_id is None:
            raise conversation_not_found()
        try:
            await require(self.session, actor, action, conversation.space_id)
        except NotFound:
            raise conversation_not_found() from None

    async def can_post(self, actor: Actor, conversation: Conversation) -> bool:
        """For a conversation the actor has read (`readable`)."""
        if conversation.archived_at is not None:
            return False
        if conversation.kind == ConversationKind.DM:
            return True
        if conversation.space_id is None:
            return False
        return await can(self.session, actor, Action.CHANNEL_POST, conversation.space_id)

    async def require_post(self, actor: Actor, conversation: Conversation) -> None:
        """The right to write in a conversation the actor has read (`readable`) now
        (403 without it, 409 archived)."""
        if conversation.kind != ConversationKind.DM:
            await self.require_in_space(actor, Action.CHANNEL_POST, conversation)
        if conversation.archived_at is not None:
            raise Conflict(code="conversation.archived")
