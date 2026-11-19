"""Notifications (spec 6.1, 6.2): what the activity view ("Für mich") lists. Reasons:
`mention` and `reply` (plan M3 decision 3); `assignment` (someone assigned me a ticket;
the message is the timeline entry of the assignment) and `ticket_comment` (a comment
on a ticket I am assigned to or reported; plan M4 decision 10); `proposal` (a page
proposal: made, for the space's moderators; decided, for its author; plan M6
decision 8: the message is the proposal's entry in the page's thread; a new page at
the top level has no thread, so its notification names the proposal and its space
instead of a conversation and a message); `skill_proposal` (a skill proposal: made,
for those who may decide it; decided, for a person author; plan M6 task 9: a skill
has no thread, so it names the proposal and its space, NULL for an organisation-wide
skill); `automation` (an automation was paused: plan M7 decisions 2 and 13; it names
the automation, `automation_id`, and no conversation: for the agent's responsible
person and the managers of the place's space when its owner lost a right, for the
owner when it kept failing); `review_due` (a page's review is due: plan M7 decision
11; the message is the entry in the page's thread, for the space's moderators,
`wiki/review_handlers.py`); `signup` (someone registered through OIDC and waits for
approval: plan M9 task 5b; it names the account, `account_id`, and no conversation:
for everyone who holds `user.manage`, `users/handlers.py`); `totp_locked` (my own
second factor was locked after too many wrong codes: review M9b F9; it names my own
account, for me alone, `totp/factor.py`); `invitation` (I was invited to an event, its
time changed, or it was cancelled or deleted: plan M10 task 4) and `invite_reply`
(someone declined or answered "maybe" to an event I organise); both name the event,
`calendar_event_id`, and no conversation, and are seen while I attend that event row
(`messaging/activity_calendar.py`). One row per person, event and reason, renewed by
each further change. The database knows three more calendar reasons that later tasks
read (`event_reminder`, `event_proposal`, `calendar_sync`): a reason gets its member
here with its reader, and the activity view lists only the reasons it knows.

A person gets at most one notification per message and reason: the unique key is
what makes the outbox handler that writes them idempotent (an event handled twice
finds its rows there and adds nothing).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow


class NotificationReason(StrEnum):
    MENTION = "mention"
    REPLY = "reply"
    ASSIGNMENT = "assignment"
    TICKET_COMMENT = "ticket_comment"
    PROPOSAL = "proposal"
    APPROVAL = "approval"  # a run's card asks me to release a tool call (plan M6 task 7)
    QUESTION = "question"  # a run's card asks me a question
    RUN_STOPPED = "run_stopped"  # a ticket's run of my agent ended or could not start
    SKILL_PROPOSAL = "skill_proposal"  # a skill proposal to decide, or mine decided
    AUTOMATION = "automation"  # an automation was paused (its owner's rights, failures)
    REVIEW_DUE = "review_due"  # a page I moderate is due for review (plan M7 task 6)
    SIGNUP = "signup"  # a self-registered account waits for approval (plan M9 task 5b)
    TOTP_LOCKED = "totp_locked"  # my second factor locked after wrong codes (M9b F9)
    INVITATION = "invitation"  # invited to an event; its time changed; it was called off
    INVITE_REPLY = "invite_reply"  # an attendee of my event declined or said "maybe"


# Every reason the database accepts: the members above and those later releases read
# (plan M10 decision 7: the check is widened once, by the migration of M10 task 4).
STORED_REASONS = (
    *(reason.value for reason in NotificationReason),
    *(
        "event_reminder",
        "event_proposal",
        "calendar_sync",
    ),
)


_TARGET_BEFORE_ACCOUNTS = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NOT NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NOT NULL)"
)
_TARGET_BEFORE_EVENTS = (
    f"(account_id IS NULL AND ({_TARGET_BEFORE_ACCOUNTS}))"
    " OR (account_id IS NOT NULL AND message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NULL AND skill_proposal_id IS NULL AND space_id IS NULL"
    " AND automation_id IS NULL)"
)
TARGET = (
    f"(calendar_event_id IS NULL AND ({_TARGET_BEFORE_EVENTS}))"
    " OR (calendar_event_id IS NOT NULL AND message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NULL AND skill_proposal_id IS NULL AND space_id IS NULL"
    " AND automation_id IS NULL AND account_id IS NULL)"
)


class Notification(UuidPk, OrgScoped, Base):
    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id", "reason"),
        CheckConstraint(
            "reason IN (" + ", ".join(f"'{reason}'" for reason in STORED_REASONS) + ")",
            name="reason",
        ),
        Index("ix_notification_user_id_id", "user_id", "id"),
        Index("ix_notification_conversation_id", "conversation_id"),
        Index("ix_notification_message_id", "message_id"),
        # Bound to a message, or (a proposal without a thread) to the proposal, or to a
        # skill proposal (in its space; none for an organisation-wide skill), or to an
        # automation.
        CheckConstraint(TARGET, name="target"),
        Index(
            "uq_notification_proposal",
            "user_id",
            "proposal_id",
            "reason",
            unique=True,
            postgresql_where=text("message_id IS NULL"),
        ),
        Index(
            "uq_notification_skill_proposal",
            "user_id",
            "skill_proposal_id",
            "reason",
            unique=True,
            postgresql_where=text("skill_proposal_id IS NOT NULL"),
        ),
        Index("ix_notification_skill_proposal_id", "skill_proposal_id"),
        Index("ix_notification_automation_id", "automation_id"),
        Index(
            "uq_notification_account",
            "user_id",
            "account_id",
            "reason",
            unique=True,
            postgresql_where=text("account_id IS NOT NULL"),
        ),
        Index("ix_notification_account_id", "account_id"),
        Index(
            "uq_notification_calendar_event",
            "user_id",
            "calendar_event_id",
            "reason",
            unique=True,
            postgresql_where=text("calendar_event_id IS NOT NULL"),
        ),
        Index("ix_notification_calendar_event_id", "calendar_event_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    reason: Mapped[NotificationReason] = mapped_column(String(16), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE")
    )
    # A proposal with no thread to tell (a new page at the top level, plan M6 task 6),
    # in its space (who may see it: the space's page editors).
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page_proposal.id", ondelete="CASCADE")
    )
    space_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE")
    )
    # A skill proposal (no thread; plan M6 task 9); who sees it: those who see the
    # proposal (`messaging/activity_sight.py`).
    skill_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill_proposal.id", ondelete="CASCADE")
    )
    # An automation that was paused (plan M7); who sees it: `activity_repository`.
    automation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("automation.id", ondelete="CASCADE")
    )
    # An account awaiting approval (plan M9 task 5b); who sees it: whoever holds
    # `user.manage` now (`activity_repository`).
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE")
    )
    # An event (plan M10 task 4); who sees it: whoever attends that event row now.
    calendar_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("calendar_event.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
