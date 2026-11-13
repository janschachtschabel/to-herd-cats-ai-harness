"""The SQL of conversations. Every statement is scoped by the actor's organisation and
by what the actor may see (`ConversationScope`), so a conversation it cannot see is
never even loaded:

- a channel: its space is one the actor may read (`access.visible_space_ids`).

Direct messages (participants) and page threads (the page's visibility) add their
clause to `_visible` (Tasks 4 and 8).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.messaging.models import Conversation, ConversationKind


@dataclass(frozen=True, slots=True)
class ConversationScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces the actor may read (SQL)
    post_space_ids: Select[uuid.UUID]  # the spaces where it holds `channel.post` (SQL)


@dataclass(frozen=True, slots=True)
class ListedConversation:
    conversation: Conversation
    can_post: bool


class ConversationRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        channel = and_(
            Conversation.kind == ConversationKind.CHANNEL,
            Conversation.space_id.in_(self.scope.space_ids),
        )
        return and_(Conversation.org_id == self.scope.org_id, or_(false(), channel))

    def _can_post(self) -> ColumnElement[bool]:
        """The right to post, before the archive (callers add that)."""
        return Conversation.space_id.in_(self.scope.post_space_ids)

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def visible(
        self, conversation_id: uuid.UUID, *, lock: bool = False
    ) -> Conversation | None:
        """The conversation if the actor may see it; with `lock`, the row as committed
        now, locked until the transaction ends."""
        stmt = (
            select(Conversation)
            .where(self._visible(), Conversation.id == conversation_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def channel_page(
        self,
        space_id: uuid.UUID | None,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
        *,
        include_archived: bool,
    ) -> list[ListedConversation]:
        """Visible channels by name (then id), of one space or of all; `after` is the
        (lower-case name, id) of the last row of the page before."""
        key = func.lower(Conversation.name)
        stmt = (
            select(Conversation, self._can_post())
            .where(self._visible(), Conversation.kind == ConversationKind.CHANNEL)
            .order_by(key, Conversation.id)
            .limit(limit)
        )
        if space_id is not None:
            stmt = stmt.where(Conversation.space_id == space_id)
        if not include_archived:
            stmt = stmt.where(Conversation.archived_at.is_(None))
        if after is not None:
            name, id_ = after
            stmt = stmt.where(or_(key > name, and_(key == name, Conversation.id > id_)))
        rows = await self.session.execute(stmt)
        return [ListedConversation(c, bool(can) and c.archived_at is None) for c, can in rows]

    async def lock_channel_names(self, space_id: uuid.UUID) -> None:
        """Serialise channel names in the space until the transaction ends, so the
        name check holds under concurrent requests (the unique index backs it up)."""
        await advisory_xact_lock(self.session, f"channel.names:{space_id}")

    async def channel_name_taken(
        self, space_id: uuid.UUID, name: str, *, besides: uuid.UUID | None = None
    ) -> bool:
        clauses = [
            Conversation.kind == ConversationKind.CHANNEL,
            Conversation.space_id == space_id,
            func.lower(Conversation.name) == name.lower(),
        ]
        if besides is not None:
            clauses.append(Conversation.id != besides)
        return bool(await self.session.scalar(select(exists().where(*clauses))))
