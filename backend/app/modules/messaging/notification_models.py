"""Notifications (spec 6.1, 6.2): what the activity view ("Für mich") lists. Reasons:
`mention` and `reply` (plan M3 decision 3); `assignment` (someone assigned me a ticket;
the message is the timeline entry of the assignment) and `ticket_comment` (a comment
on a ticket I am assigned to or reported; plan M4 decision 10).

A person gets at most one notification per message and reason: the unique key is
what makes the outbox handler that writes them idempotent (an event handled twice
finds its rows there and adds nothing).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow


class NotificationReason(StrEnum):
    MENTION = "mention"
    REPLY = "reply"
    ASSIGNMENT = "assignment"
    TICKET_COMMENT = "ticket_comment"


class Notification(UuidPk, OrgScoped, Base):
    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id", "reason"),
        CheckConstraint(
            "reason IN ('mention', 'reply', 'assignment', 'ticket_comment')", name="reason"
        ),
        Index("ix_notification_user_id_id", "user_id", "id"),
        Index("ix_notification_conversation_id", "conversation_id"),
        Index("ix_notification_message_id", "message_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    reason: Mapped[NotificationReason] = mapped_column(String(16), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
