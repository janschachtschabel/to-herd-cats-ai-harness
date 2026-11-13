"""What people do with messages besides writing them (spec 6.1): mention someone,
react, and read up to a point.

- `message_mention`: a person mentioned in a message; stored only for people who may
  see the conversation when the message is written or edited.
- `reaction`: one emoji (`emoji.is_emoji`) per person and message at most once.
- `conversation_read`: how far a person has read a conversation (a message id;
  UUIDv7, so later messages have greater ids); it only moves forward.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, utcnow
from app.modules.messaging.emoji import MAX_EMOJI_CHARS


class MessageMention(OrgScoped, Base):
    __tablename__ = "message_mention"
    __table_args__ = (Index("ix_message_mention_user_id", "user_id", "message_id"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True
    )


class Reaction(OrgScoped, Base):
    __tablename__ = "reaction"

    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True
    )
    emoji: Mapped[str] = mapped_column(String(MAX_EMOJI_CHARS), primary_key=True)
    # Orders a message's reactions: the emoji reacted with first comes first.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ConversationRead(OrgScoped, Base):
    __tablename__ = "conversation_read"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True
    )
    last_read_message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE"), nullable=False
    )
