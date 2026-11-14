"""Conversations and their messages (spec 6.1). One model for every kind of
conversation:

- `channel`: belongs to a space and is seen by whoever may read it. Its name is
  unique in its space, ignoring case, archived channels included.
- `dm`: a direct message between 2 and 9 people (`conversation_participant`), in no
  space, seen only by its participants. `dm_key` (a hash of the sorted participants)
  is unique per organisation, so the same group always meets in the same
  conversation; participants never change. An admin reads one only through an
  inspection (`dm_inspection`, spec 5.5).

- `thread_page`: the discussion of one wiki page (`page_id`, unique), in the page's
  space, seen by whoever sees the page (drafts with `page.edit`, nothing while the
  page is in the trash), removed with the page when it is purged.
- `thread_ticket`: the discussion of one ticket (`work_item_id`, unique), in the
  ticket's space, seen by whoever may read tickets there; it comes with the ticket.

Messages: top level (`parent_id` NULL) or a reply to a top-level message of the same
conversation (one level; the services check it). A top-level message counts its
replies (`reply_count`, `last_reply_at`), kept in the reply's transaction under a row
lock on the parent. Deleting is soft: `deleted_at` is set and the text emptied.
`system` messages (spec 6.2) exist only in page and ticket threads and (M5) in a DM
with an agent, where they say why a run stopped; `agent` messages (an agent's answer)
only in a DM the agent takes part in. Database triggers (migrations m3 messages, m4
ticket threads, m5 agents) refuse them anywhere else and refuse to change a
conversation's kind.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Computed,
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
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.core.principal import PrincipalType

MAX_CHANNEL_NAME_CHARS = 80
MAX_TOPIC_CHARS = 250
MAX_BODY_CHARS = 20_000


MIN_DM_PEOPLE = 2
MAX_DM_PEOPLE = 9
MAX_REASON_CHARS = 500


class ConversationKind(StrEnum):
    CHANNEL = "channel"
    DM = "dm"
    THREAD_PAGE = "thread_page"
    THREAD_TICKET = "thread_ticket"


class Conversation(UuidPk, OrgScoped, Base):
    __tablename__ = "conversation"
    __table_args__ = (
        CheckConstraint("kind IN ('channel', 'dm', 'thread_page', 'thread_ticket')", name="kind"),
        CheckConstraint(
            "kind <> 'channel' OR (space_id IS NOT NULL AND name IS NOT NULL)",
            name="channel_fields",
        ),
        CheckConstraint(
            "(kind = 'dm') = (dm_key IS NOT NULL)"
            " AND (kind <> 'dm' OR (space_id IS NULL AND name IS NULL AND topic IS NULL))",
            name="dm_fields",
        ),
        UniqueConstraint("org_id", "dm_key"),
        CheckConstraint(
            "(kind = 'thread_page') = (page_id IS NOT NULL)"
            " AND (kind <> 'thread_page' OR (space_id IS NOT NULL AND name IS NULL"
            " AND topic IS NULL))",
            name="thread_fields",
        ),
        UniqueConstraint("page_id"),
        CheckConstraint(
            "(kind = 'thread_ticket') = (work_item_id IS NOT NULL)"
            " AND (kind <> 'thread_ticket' OR (space_id IS NOT NULL AND name IS NULL"
            " AND topic IS NULL))",
            name="ticket_thread_fields",
        ),
        UniqueConstraint("work_item_id"),
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
    # A direct message's participants, as a hash (`dms.dm_key`); NULL for other kinds.
    dm_key: Mapped[str | None] = mapped_column(String(64))
    # A page thread's page; NULL for other kinds.
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE")
    )
    # A ticket thread's ticket; NULL for other kinds.
    work_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_item.id", ondelete="CASCADE")
    )
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


class ConversationParticipant(OrgScoped, Base):
    """A person in a direct message, or (M5) the one agent of a DM with one person."""

    __tablename__ = "conversation_participant"
    __table_args__ = (
        CheckConstraint("principal_type IN ('user', 'agent')", name="principal_type"),
        Index("ix_conversation_participant_principal", "principal_type", "principal_id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), primary_key=True
    )
    principal_type: Mapped[PrincipalType] = mapped_column(String(16), primary_key=True)
    principal_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)


class DmInspection(UuidPk, OrgScoped, Base):
    """An admin's read-only look into a direct message (spec 5.5): with a reason, for a
    limited time, recorded in the audit log, shown to the participants."""

    __tablename__ = "dm_inspection"
    __table_args__ = (
        CheckConstraint(f"char_length(reason) <= {MAX_REASON_CHARS}", name="reason_length"),
        CheckConstraint("expires_at > granted_at", name="expiry"),
        Index("ix_dm_inspection_conversation_id", "conversation_id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# Full-text search (plan M3 task 9): configured like a page's content (German stems).
MESSAGE_TSV_SQL = "to_tsvector('german'::regconfig, body_md)"
# The messages search finds: written by people and not deleted (the index predicate).
SEARCHABLE_SQL = "kind = 'human' AND deleted_at IS NULL"


class MessageKind(StrEnum):
    HUMAN = "human"
    # Page and ticket threads, and a DM with an agent (a run's stop; database triggers).
    SYSTEM = "system"
    AGENT = "agent"  # an agent's answer, in a DM it takes part in; `client_id` = the run


SYSTEM_AUTHOR = "system"  # `author_type` of system messages, which have no author id


class Message(UuidPk, OrgScoped, Base):
    __tablename__ = "message"
    __table_args__ = (
        # A resend with the same key returns the first message (idempotent posting).
        UniqueConstraint("author_id", "client_id"),
        CheckConstraint("kind IN ('human', 'system', 'agent')", name="kind"),
        CheckConstraint("author_type IN ('user', 'system', 'agent')", name="author_type"),
        CheckConstraint(
            "(kind = 'system') = (author_type = 'system')"
            " AND (author_type = 'system') = (author_id IS NULL)"
            " AND (kind = 'agent') = (author_type = 'agent')",
            name="author",
        ),
        # An agent's answer names its run (`client_id`), once (with the unique key above).
        CheckConstraint("kind <> 'agent' OR client_id IS NOT NULL", name="agent_run"),
        CheckConstraint(f"char_length(body_md) <= {MAX_BODY_CHARS}", name="body_length"),
        # A system message names the event it was written for (`client_id`), once.
        CheckConstraint("author_type <> 'system' OR client_id IS NOT NULL", name="system_event"),
        Index(
            "uq_message_system_client_id",
            "client_id",
            unique=True,
            postgresql_where=text("author_type = 'system'"),
        ),
        Index(
            "ix_message_conversation_id_top",
            "conversation_id",
            "id",
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index("ix_message_parent_id", "parent_id", "id"),
        Index(
            "ix_message_search_tsv",
            "search_tsv",
            postgresql_using="gin",
            postgresql_where=text(SEARCHABLE_SQL),
        ),
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
    # Read only by the search's SQL; deferred, so loading a message does not load it.
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed(MESSAGE_TSV_SQL, persisted=True), deferred=True
    )
