"""The SQL of notifications: writing them (the outbox handler, in the event's
organisation) and a person's activity view.

The activity view filters in SQL: only the person's own notifications, only those
whose conversation the person may see now (`visible_conversations`), and only for
messages that are not deleted. A notification from a conversation gone from view
disappears from the list, the counters and the marking routes at once.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.messaging.models import Conversation, ConversationKind, Message
from app.modules.messaging.notification_models import Notification, NotificationReason
from app.modules.messaging.repository import ConversationScope, visible_conversations
from app.modules.users.models import User

SNIPPET_CHARS = 140


@dataclass(frozen=True, slots=True)
class ActivityEntry:
    notification: Notification
    conversation_kind: ConversationKind
    conversation_name: str | None
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None  # a page thread's page
    parent_id: uuid.UUID | None  # the thread the message is in, if any
    author_id: uuid.UUID | None
    author_name: str | None
    snippet: str  # the start of the message's Markdown


class NotificationRepository:
    """Writing notifications, for the outbox handler (no actor: the event's org)."""

    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def message(self, message_id: uuid.UUID) -> Message | None:
        stmt = select(Message).where(Message.org_id == self.org_id, Message.id == message_id)
        return await self.session.scalar(stmt)

    async def thread_people(self, parent: Message, reply: Message) -> set[uuid.UUID]:
        """The people who wrote the thread's top message or a reply before `reply`
        (later replies are not its audience, also when an event comes again later)."""
        stmt = select(Message.author_id).where(
            Message.org_id == self.org_id,
            Message.parent_id == parent.id,
            Message.id < reply.id,
            Message.author_type == "user",
        )
        people = {author for author in await self.session.scalars(stmt) if author is not None}
        if parent.author_type == "user" and parent.author_id is not None:
            people.add(parent.author_id)
        return people

    async def add(
        self, message: Message, wanted: Sequence[tuple[uuid.UUID, NotificationReason]]
    ) -> list[Notification]:
        """The notifications of `wanted` that did not exist yet."""
        if not wanted:
            return []
        rows = [
            {
                "org_id": self.org_id,
                "user_id": user_id,
                "reason": reason,
                "conversation_id": message.conversation_id,
                "message_id": message.id,
            }
            for user_id, reason in wanted
        ]
        stmt = (
            insert(Notification)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["user_id", "message_id", "reason"])
            .returning(Notification)
        )
        return list((await self.session.scalars(stmt)).all())


class ActivityRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    def _mine(self) -> ColumnElement[bool]:
        # Self-contained subqueries: the list joins `conversation` and `message` too.
        seen = select(Conversation.id).where(visible_conversations(self.scope)).correlate(None)
        kept = aliased(Message)
        live = (
            select(kept.id)
            .where(kept.id == Notification.message_id, kept.deleted_at.is_(None))
            .correlate_except(kept)
        )
        return and_(
            Notification.org_id == self.scope.org_id,
            Notification.user_id == self.scope.principal.id,
            Notification.conversation_id.in_(seen),
            live.exists(),
        )

    async def page(
        self, before: uuid.UUID | None, limit: int, *, only_open: bool
    ) -> list[ActivityEntry]:
        """The person's notifications, newest first."""
        stmt = (
            select(
                Notification,
                Conversation.kind,
                Conversation.name,
                Conversation.space_id,
                Conversation.page_id,
                Message.parent_id,
                Message.author_id,
                User.name,
                func.left(Message.body_md, SNIPPET_CHARS),
            )
            .join(Conversation, Conversation.id == Notification.conversation_id)
            .join(Message, Message.id == Notification.message_id)
            .outerjoin(User, User.id == Message.author_id)
            .where(self._mine())
            .order_by(Notification.id.desc())
            .limit(limit)
        )
        if only_open:
            stmt = stmt.where(Notification.done_at.is_(None))
        if before is not None:
            stmt = stmt.where(Notification.id < before)
        return [ActivityEntry(*row) for row in await self.session.execute(stmt)]

    async def counts(self) -> tuple[int, int]:
        """(open, unread): not done; not done and not read."""
        open_ = Notification.done_at.is_(None)
        stmt = select(
            func.count().filter(open_),
            func.count().filter(open_, Notification.read_at.is_(None)),
        ).where(self._mine())
        row = (await self.session.execute(stmt)).one()
        return int(row[0]), int(row[1])

    async def mark(self, notification_id: uuid.UUID | None, *, done: bool) -> int:
        """Mark one notification (or, with None, every unread one) read, or done (and
        read); how many changed (a repeat changes nothing)."""
        stmt = update(Notification).where(self._mine())
        if notification_id is not None:
            stmt = stmt.where(Notification.id == notification_id)
        if done:
            stmt = stmt.where(Notification.done_at.is_(None)).values(
                done_at=func.now(), read_at=func.coalesce(Notification.read_at, func.now())
            )
        else:
            stmt = stmt.where(Notification.read_at.is_(None)).values(read_at=func.now())
        changed = await self.session.execute(stmt.returning(Notification.id))
        return len(changed.all())

    async def exists(self, notification_id: uuid.UUID) -> bool:
        stmt = select(Notification.id).where(self._mine(), Notification.id == notification_id)
        return await self.session.scalar(stmt) is not None
