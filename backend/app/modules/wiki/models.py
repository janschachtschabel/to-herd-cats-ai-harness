"""Wiki pages and their versions (spec 9). Markdown in `content_md` is the only stored
form of a page.

`path` is the slugs from the root down, joined by `/`; it is unique in a space among
the pages that are not in the trash, and rewritten for a whole subtree when a page
moves. Pages in the trash keep the path they had, so a restore knows where they were.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk, utcnow
from app.core.principal import PrincipalType

MAX_DEPTH = 16  # path segments
MAX_CONTENT_CHARS = 200_000
MAX_TITLE_CHARS = 200
MAX_SLUG_CHARS = 80
MAX_SUMMARY_CHARS = 300
MAX_LABEL_CHARS = 100
MAX_FILENAME_CHARS = 255


# Full-text search (spec 11): the title stemmed (German) and as written (simple), both
# weighted above the content. Kept up to date by Postgres on every write.
SEARCH_TSV_SQL = (
    "setweight(to_tsvector('german'::regconfig, title), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, title), 'A') || "
    "setweight(to_tsvector('german'::regconfig, content_md), 'B')"
)


class PageStatus(StrEnum):
    DRAFT = "draft"  # seen only by those who may edit pages in the space
    PUBLISHED = "published"


class Page(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "page"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="status"),
        Index(
            "uq_page_space_id_path_live",
            "space_id",
            "path",
            unique=True,
            postgresql_where=text("trashed_at IS NULL"),
        ),
        Index("ix_page_space_id_parent_id", "space_id", "parent_id"),
        Index("ix_page_search_tsv", "search_tsv", postgresql_using="gin"),
        Index("ix_page_parent_id", "parent_id"),
        Index(
            "ix_page_space_id_reviewed_at",
            "space_id",
            "reviewed_at",
            postgresql_where=text("trashed_at IS NULL AND status = 'published'"),
        ),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    # No cascade: a page leaves only with its whole subtree (trash, purge).
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id")
    )
    title: Mapped[str] = mapped_column(String(MAX_TITLE_CHARS), nullable=False)
    slug: Mapped[str] = mapped_column(String(MAX_SLUG_CHARS), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[PageStatus] = mapped_column(String(16), default=PageStatus.DRAFT, nullable=False)
    # Bumped by every write to the row; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Bumped by every change that ends open live-editing sessions (spec 9).
    collab_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    updated_by_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The last review (plan M7 decision 11, `review.py`): set when the page is published
    # and by "mark as reviewed"; NULL for a draft. `review_notified_at`: when the daily
    # pass last emitted `page.review_due` for it (once per interval); NULL again with
    # every review. Neither bumps `version` or `updated_at`.
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Locked for AI (spec 11): no tool returns it, no embeddings (`ai/policy_filters.py`).
    no_ai: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Read only by the search's SQL; deferred, so loading a page does not load it.
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed(SEARCH_TSV_SQL, persisted=True), deferred=True
    )


# The search's title prefix, `lower(title) LIKE 'q%'` (review M2 R19).
Index(
    "ix_page_title_prefix",
    func.lower(Page.title).label("title_lower"),
    postgresql_ops={"title_lower": "text_pattern_ops"},
)


class VersionSource(StrEnum):
    HUMAN = "human"  # saved by someone through the API
    IMPORT = "import"
    RESTORE = "restore"  # an older state brought back as a new version
    COLLAB = "collab"  # saved from a live-editing session
    AGENT = "agent"  # written for an agent (its run, or a proposal of it accepted)


class PageVersion(UuidPk, OrgScoped, Base):
    """A saved state of a page, numbered 1, 2, … per page. Versions of one author in
    one live session are folded into one within a short window (`session_key`)."""

    __tablename__ = "page_version"
    __table_args__ = (
        UniqueConstraint("page_id", "number"),
        CheckConstraint(
            "source IN ('human', 'import', 'restore', 'collab', 'agent')", name="source"
        ),
    )

    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(MAX_TITLE_CHARS), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    author_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source: Mapped[VersionSource] = mapped_column(String(16), nullable=False)
    # Free text, or `restore:<n>` for a restore (the client words it).
    change_summary: Mapped[str | None] = mapped_column(String(MAX_SUMMARY_CHARS))
    label: Mapped[str | None] = mapped_column(String(MAX_LABEL_CHARS))
    session_key: Mapped[str | None] = mapped_column(String(100))
    # The agent's run that wrote it (no foreign key: a version outlives its run, like
    # `usage_record.run_id`); the AI mark is an agent as author (`version_schemas`).
    run_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Attachment(UuidPk, OrgScoped, Base):
    """A file on a page, readable by whoever may read the page. The bytes live in the
    storage under `storage_key` (`attachments/<org_id>/<sha256>`), shared by every
    attachment of the organisation with the same content."""

    __tablename__ = "attachment"
    __table_args__ = (
        Index("ix_attachment_page_id", "page_id"),
        Index("ix_attachment_org_id_sha256", "org_id", "sha256"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    # Purging a page deletes its attachments (and unused files) first; the cascade
    # only backs that up.
    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(MAX_FILENAME_CHARS), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(200), nullable=False)
    uploaded_by_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # Locked for AI (spec 11), like a page; a file on a locked page counts as locked.
    no_ai: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Bumped by the lock (the attachment's only write); a write names the version it read.
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
