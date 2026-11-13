"""Conversations and their messages (spec 6.1). One model for every kind of
conversation; M3 begins with channels (`kind = channel`), which belong to a space and
are seen by whoever may read it. Direct messages and page threads add their kinds,
columns and checks with their own migrations (Tasks 4 and 8).

A channel's name is unique in its space, ignoring case, archived channels included.

Messages: top level (`parent_id` NULL) or a reply to a top-level message of the same
conversation (one level; the services check it). A top-level message counts its
replies (`reply_count`, `last_reply_at`), kept in the reply's transaction under a row
lock on the parent. Deleting is soft: `deleted_at` is set and the text emptied.
`system` messages (spec 6.2) exist only in page threads; database triggers
(migration m3 messages) refuse them anywhere else and refuse to change a
conversation's kind.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.core.principal import PrincipalType

MAX_CHANNEL_NAME_CHARS = 80
MAX_TOPIC_CHARS = 250
MAX_BODY_CHARS = 20_000


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


class MessageKind(StrEnum):
    HUMAN = "human"
    SYSTEM = "system"  # page threads only (database triggers)


SYSTEM_AUTHOR = "system"  # `author_type` of system messages, which have no author id


class Message(UuidPk, OrgScoped, Base):
    __tablename__ = "message"
    __table_args__ = (
        # A resend with the same key returns the first message (idempotent posting).
        UniqueConstraint("author_id", "client_id"),
        CheckConstraint("kind IN ('human', 'system')", name="kind"),
        CheckConstraint("author_type IN ('user', 'system')", name="author_type"),
        CheckConstraint(
            "(kind = 'system') = (author_type = 'system')"
            " AND (author_type = 'system') = (author_id IS NULL)",
            name="author",
        ),
        CheckConstraint(f"char_length(body_md) <= {MAX_BODY_CHARS}", name="body_length"),
        Index(
            "ix_message_conversation_id_top",
            "conversation_id",
            "id",
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index("ix_message_parent_id", "parent_id", "id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE")
    )
    author_type: Mapped[str] = mapped_column(String(16), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    kind: Mapped[MessageKind] = mapped_column(String(16), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
