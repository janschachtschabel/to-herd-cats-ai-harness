"""The SQL of mentions, reactions and read positions. Callers pass messages and
conversations the actor has been allowed to see; the unread counters filter by the
actor's visibility themselves, at the time of asking (review focus 5).
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import Conversation, ConversationKind, Message, MessageKind
from app.modules.messaging.repository import ConversationScope, visible_conversations
from app.modules.messaging.social_models import ConversationRead, MessageMention, Reaction


@dataclass(frozen=True, slots=True)
class ReactionSummary:
    emoji: str
    count: int
    mine: bool


@dataclass(frozen=True, slots=True)
class Unread:
    conversation_id: uuid.UUID
    unread: int  # others' top-level messages after the read position, not deleted
    mentions: int  # mentions of the person after it, in replies too


class MentionRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def replace(self, message_id: uuid.UUID, user_ids: Iterable[uuid.UUID]) -> None:
        """The message mentions exactly `user_ids` from now on."""
        keep = list(user_ids)
        await self.session.execute(
            delete(MessageMention).where(
                MessageMention.message_id == message_id, MessageMention.user_id.not_in(keep)
            )
        )
        if keep:
            rows = [{"org_id": self.org_id, "message_id": message_id, "user_id": u} for u in keep]
            await self.session.execute(insert(MessageMention).values(rows).on_conflict_do_nothing())

    async def of(self, message_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
        """Who each message mentions."""
        found: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        if not message_ids:
            return found
        stmt = (
            select(MessageMention.message_id, MessageMention.user_id)
            .where(MessageMention.org_id == self.org_id, MessageMention.message_id.in_(message_ids))
            .order_by(MessageMention.message_id, MessageMention.user_id)
        )
        for message_id, user_id in await self.session.execute(stmt):
            found[message_id].append(user_id)
        return found


class ReactionRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def add(self, message_id: uuid.UUID, user_id: uuid.UUID, emoji: str) -> bool:
        """True if the reaction is new."""
        stmt = (
            insert(Reaction)
            .values(org_id=self.org_id, message_id=message_id, user_id=user_id, emoji=emoji)
            .on_conflict_do_nothing()
            .returning(Reaction.message_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def remove(self, message_id: uuid.UUID, user_id: uuid.UUID, emoji: str) -> bool:
        """True if there was such a reaction."""
        stmt = (
            delete(Reaction)
            .where(
                Reaction.org_id == self.org_id,
                Reaction.message_id == message_id,
                Reaction.user_id == user_id,
                Reaction.emoji == emoji,
            )
            .returning(Reaction.message_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def summaries(
        self, message_ids: Sequence[uuid.UUID], user_id: uuid.UUID
    ) -> dict[uuid.UUID, list[ReactionSummary]]:
        """Each message's reactions by emoji (first reacted first), with whether
        `user_id` is among them."""
        found: dict[uuid.UUID, list[ReactionSummary]] = defaultdict(list)
        if not message_ids:
            return found
        first = func.min(Reaction.created_at)
        stmt = (
            select(
                Reaction.message_id,
                Reaction.emoji,
                func.count(),
                func.bool_or(Reaction.user_id == user_id),
            )
            .where(Reaction.org_id == self.org_id, Reaction.message_id.in_(message_ids))
            .group_by(Reaction.message_id, Reaction.emoji)
            .order_by(Reaction.message_id, first, Reaction.emoji)
        )
        for message_id, emoji, count, mine in await self.session.execute(stmt):
            found[message_id].append(ReactionSummary(emoji, count, bool(mine)))
        return found


class ReadRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    async def advance(self, conversation_id: uuid.UUID, message_id: uuid.UUID) -> bool:
        """Move the person's position forward to `message_id`; False if it was there
        or further already."""
        me = self.scope.principal.id
        row = insert(ConversationRead).values(
            org_id=self.scope.org_id,
            conversation_id=conversation_id,
            user_id=me,
            last_read_message_id=message_id,
        )
        newer = row.excluded.last_read_message_id
        stmt = row.on_conflict_do_update(
            index_elements=["conversation_id", "user_id"],
            set_={"last_read_message_id": newer},
            where=ConversationRead.last_read_message_id < newer,
        ).returning(ConversationRead.conversation_id)
        return (await self.session.execute(stmt)).first() is not None

    async def position(self, conversation_id: uuid.UUID) -> tuple[uuid.UUID, datetime] | None:
        """The person's position in the conversation and when that message was
        written; None before she read anything there."""
        stmt = (
            select(ConversationRead.last_read_message_id, Message.created_at)
            .join(Message, Message.id == ConversationRead.last_read_message_id)
            .where(
                ConversationRead.org_id == self.scope.org_id,
                ConversationRead.conversation_id == conversation_id,
                ConversationRead.user_id == self.scope.principal.id,
            )
        )
        row = (await self.session.execute(stmt)).first()
        return None if row is None else (row[0], row[1])

    async def unread_page(self, after: uuid.UUID | None, limit: int) -> list[Unread]:
        """The person's visible conversations with something unread, by id."""
        me = self.scope.principal.id
        position = (
            select(ConversationRead.last_read_message_id)
            .where(
                ConversationRead.conversation_id == Conversation.id, ConversationRead.user_id == me
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        unseen: ColumnElement[bool] = and_(
            Message.conversation_id == Conversation.id,
            Message.deleted_at.is_(None),
            Message.kind == MessageKind.HUMAN,  # a page's timeline is nothing to read
            Message.author_id.is_distinct_from(me),
            or_(position.is_(None), Message.id > position),
        )
        unread = (
            select(func.count())
            .select_from(Message)
            .where(unseen, Message.parent_id.is_(None))
            .correlate(Conversation)
            .scalar_subquery()
        )
        mentions = (
            select(func.count())
            .select_from(MessageMention)
            .join(Message, Message.id == MessageMention.message_id)
            .where(unseen, MessageMention.user_id == me)
            .correlate(Conversation)
            .scalar_subquery()
        )
        counted = select(
            Conversation.id.label("conversation_id"),
            unread.label("unread"),
            mentions.label("mentions"),
        ).where(
            visible_conversations(self.scope),
            # A page's discussion counts once the person has opened it (read in it).
            or_(Conversation.kind != ConversationKind.THREAD_PAGE, position.is_not(None)),
        )
        if after is not None:
            counted = counted.where(Conversation.id > after)
        rows = counted.subquery()
        stmt = (
            select(rows.c.conversation_id, rows.c.unread, rows.c.mentions)
            .where(or_(rows.c.unread > 0, rows.c.mentions > 0))
            .order_by(rows.c.conversation_id)
            .limit(limit)
        )
        return [Unread(*row) for row in await self.session.execute(stmt)]
