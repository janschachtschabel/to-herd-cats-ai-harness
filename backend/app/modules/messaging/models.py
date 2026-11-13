"""Conversations (spec 6.1). One model for every kind of conversation; M3 begins with
channels (`kind = channel`), which belong to a space and are seen by whoever may read
it. Direct messages and page threads add their kinds, columns and checks with their
own migrations (Tasks 4 and 8).

A channel's name is unique in its space, ignoring case, archived channels included.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.core.principal import PrincipalType

MAX_CHANNEL_NAME_CHARS = 80
MAX_TOPIC_CHARS = 250


class ConversationKind(StrEnum):
    CHANNEL = "channel"


class Conversation(UuidPk, OrgScoped, Base):
    __tablename__ = "conversation"
    __table_args__ = (
        CheckConstraint("kind IN ('channel')", name="kind"),
        CheckConstraint(
            "kind <> 'channel' OR (space_id IS NOT NULL AND name IS NOT NULL)",
            name="channel_fields",
        ),
        CheckConstraint(
            "(created_by_type IS NULL) = (created_by_id IS NULL)", name="created_by_pair"
        ),
        Index("ix_conversation_space_id", "space_id"),
    )

    kind: Mapped[ConversationKind] = mapped_column(String(16), nullable=False)
    space_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE")
    )
    name: Mapped[str | None] = mapped_column(String(MAX_CHANNEL_NAME_CHARS))
    topic: Mapped[str | None] = mapped_column(String(MAX_TOPIC_CHARS))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Who created it; NULL for what the system set up (`#allgemein`).
    created_by_type: Mapped[PrincipalType | None] = mapped_column(String(16))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # Bumped by every change to the row; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# A channel's name, unique in its space without regard to case.
Index(
    "uq_conversation_channel_name",
    Conversation.space_id,
    func.lower(Conversation.name).label("name_lower"),
    unique=True,
    postgresql_where=text("kind = 'channel'"),
)
