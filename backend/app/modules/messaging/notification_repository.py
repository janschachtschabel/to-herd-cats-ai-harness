"""Writing notifications (the outbox handlers, in the event's organisation; no actor).
A person's activity view: `activity_repository.py`."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.messaging.models import Message
from app.modules.messaging.notification_models import Notification, NotificationReason


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

    async def add_for_proposal(
        self,
        proposal_id: uuid.UUID,
        space_id: uuid.UUID,
        wanted: Sequence[tuple[uuid.UUID, NotificationReason]],
    ) -> list[Notification]:
        """Notifications about a proposal with no thread to point at, those that did
        not exist yet."""
        if not wanted:
            return []
        rows = [
            {
                "org_id": self.org_id,
                "user_id": user_id,
                "reason": reason,
                "proposal_id": proposal_id,
                "space_id": space_id,
            }
            for user_id, reason in wanted
        ]
        stmt = (
            insert(Notification)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["user_id", "proposal_id", "reason"],
                index_where=Notification.message_id.is_(None),
            )
            .returning(Notification)
        )
        return list((await self.session.scalars(stmt)).all())

    async def withdraw_mentions(
        self, message: Message, keep: Sequence[uuid.UUID]
    ) -> list[uuid.UUID]:
        """Remove the unread `mention` notifications of `message` for people not in
        `keep`; whose they were."""
        stmt = (
            delete(Notification)
            .where(
                Notification.org_id == self.org_id,
                Notification.message_id == message.id,
                Notification.reason == NotificationReason.MENTION,
                Notification.read_at.is_(None),
                Notification.user_id.not_in(keep),
            )
            .returning(Notification.user_id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def add_for_skill_proposal(
        self,
        proposal_id: uuid.UUID,
        space_id: uuid.UUID | None,
        wanted: Sequence[tuple[uuid.UUID, NotificationReason]],
    ) -> list[Notification]:
        """Notifications about a skill proposal (it has no thread), those that did not
        exist yet; `space_id` is its space (none: organisation-wide)."""
        if not wanted:
            return []
        rows = [
            {
                "org_id": self.org_id,
                "user_id": user_id,
                "reason": reason,
                "skill_proposal_id": proposal_id,
                "space_id": space_id,
            }
            for user_id, reason in wanted
        ]
        stmt = (
            insert(Notification)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["user_id", "skill_proposal_id", "reason"],
                index_where=Notification.skill_proposal_id.is_not(None),
            )
            .returning(Notification)
        )
        return list((await self.session.scalars(stmt)).all())

    async def add_for_automation(
        self, automation_id: uuid.UUID, wanted: Sequence[tuple[uuid.UUID, NotificationReason]]
    ) -> list[Notification]:
        """Notifications about an automation (it has no thread). Not unique: each
        pause tells again (the due loop and a run's end write them once, in their
        transaction)."""
        if not wanted:
            return []
        rows = [
            {"org_id": self.org_id, "user_id": u, "reason": r, "automation_id": automation_id}
            for u, r in wanted
        ]
        stmt = insert(Notification).values(rows).returning(Notification)
        return list((await self.session.scalars(stmt)).all())

    async def add_for_account(
        self, account_id: uuid.UUID, wanted: Sequence[tuple[uuid.UUID, NotificationReason]]
    ) -> list[Notification]:
        """Notifications about an account awaiting approval (plan M9 task 5b), those
        that did not exist yet."""
        if not wanted:
            return []
        rows = [
            {"org_id": self.org_id, "user_id": user_id, "reason": reason, "account_id": account_id}
            for user_id, reason in wanted
        ]
        stmt = (
            insert(Notification)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["user_id", "account_id", "reason"],
                index_where=Notification.account_id.is_not(None),
            )
            .returning(Notification)
        )
        return list((await self.session.scalars(stmt)).all())

    async def renew_about_account(
        self, user_id: uuid.UUID, account_id: uuid.UUID, reason: NotificationReason
    ) -> None:
        """One unread notification about an account for `user_id`, new each time (an
        earlier one of the same reason goes: the person sees the latest on top)."""
        await self.session.execute(
            delete(Notification).where(
                Notification.org_id == self.org_id,
                Notification.user_id == user_id,
                Notification.account_id == account_id,
                Notification.reason == reason,
            )
        )
        await self.add_for_account(account_id, [(user_id, reason)])

    async def renew_about_event(
        self,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
        reason: NotificationReason,
        cause_at: datetime,
    ) -> Notification | None:
        """The one notification about a calendar event for `user_id` and `reason`,
        renewed for a cause written at `cause_at` (unread, on top: an earlier one goes)
        unless the stored one is not older than the cause (a redelivered cause leaves it
        as it is, read or not: review M10 task 4, R4-2); None if nothing new was written
        (that, or a concurrent delivery wrote it first). A new one is dated no earlier
        than its cause, so a node whose clock is behind still sees it as current."""
        await self.session.execute(
            delete(Notification).where(
                Notification.org_id == self.org_id,
                Notification.user_id == user_id,
                Notification.calendar_event_id == event_id,
                Notification.reason == reason,
                Notification.created_at < cause_at,
            )
        )
        row = {
            "org_id": self.org_id,
            "user_id": user_id,
            "reason": reason,
            "calendar_event_id": event_id,
            "created_at": max(utcnow(), cause_at),
        }
        stmt = (
            insert(Notification)
            .values([row])
            .on_conflict_do_nothing(
                index_elements=["user_id", "calendar_event_id", "reason"],
                index_where=Notification.calendar_event_id.is_not(None),
            )
            .returning(Notification)
        )
        renewed: Notification | None = await self.session.scalar(stmt)
        return renewed
