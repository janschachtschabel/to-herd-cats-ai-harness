"""The SQL of messages. Every statement is scoped by the actor's organisation and the
conversations it may see (`visible_conversations`), so a message in a conversation
the actor cannot see is never even loaded.

Ids are UUIDv7, so ordering by id is ordering by creation time.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import Conversation, Message, MessageKind
from app.modules.messaging.repository import ConversationScope, visible_conversations


class MessageRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        seen = select(Conversation.id).where(visible_conversations(self.scope))
        return and_(Message.org_id == self.scope.org_id, Message.conversation_id.in_(seen))

    async def get(self, message_id: uuid.UUID, *, lock: bool = False) -> Message | None:
        """The message if the actor may see its conversation; with `lock`, the row as
        committed now, locked until the transaction ends."""
        stmt = (
            select(Message)
            .where(self._visible(), Message.id == message_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def fresh_start_held(self, conversation_id: uuid.UUID) -> datetime | None:
        """The conversation's fresh start as committed now, its row held `FOR SHARE`
        until the transaction ends, so a fresh start (`agents/fresh_start.py`) cannot
        come between this and the commit (module review M8 4, K4)."""
        stmt = (
            select(Conversation.fresh_start_at)
            .where(Conversation.org_id == self.scope.org_id, Conversation.id == conversation_id)
            .with_for_update(read=True)
        )
        return await self.session.scalar(stmt)

    async def insert(self, values: dict[str, Any]) -> Message | None:
        """A new message; None when its author has used its `client_id` before (the
        first one wins, also against a concurrent insert, which is waited for)."""
        stmt = (
            insert(Message)
            .values(org_id=self.scope.org_id, **values)
            .on_conflict_do_nothing(index_elements=["author_id", "client_id"])
            .returning(Message)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def by_client_id(self, author_id: uuid.UUID, client_id: uuid.UUID) -> Message | None:
        """The author's message sent with that key (in the organisation)."""
        stmt = select(Message).where(
            Message.org_id == self.scope.org_id,
            Message.author_id == author_id,
            Message.client_id == client_id,
        )
        return await self.session.scalar(stmt)

    async def top_page(
        self,
        conversation_id: uuid.UUID,
        limit: int,
        *,
        older_than: uuid.UUID | None = None,
        newer_than: uuid.UUID | None = None,
        human_only: bool = False,
    ) -> list[Message]:
        """Top-level messages of a conversation: newest first, older than `older_than`;
        or, with `newer_than`, oldest first from just after it. With `human_only`,
        without system messages."""
        stmt = select(Message).where(
            self._visible(),
            Message.conversation_id == conversation_id,
            Message.parent_id.is_(None),
        )
        if human_only:
            stmt = stmt.where(Message.kind == MessageKind.HUMAN)
        if newer_than is not None:
            stmt = stmt.where(Message.id > newer_than).order_by(Message.id)
        else:
            if older_than is not None:
                stmt = stmt.where(Message.id < older_than)
            stmt = stmt.order_by(Message.id.desc())
        return list((await self.session.scalars(stmt.limit(limit))).all())

    async def reply_page(
        self, parent_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[Message]:
        """Replies to a message, oldest first."""
        stmt = (
            select(Message)
            .where(self._visible(), Message.parent_id == parent_id)
            .order_by(Message.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(Message.id > after)
        return list((await self.session.scalars(stmt)).all())
