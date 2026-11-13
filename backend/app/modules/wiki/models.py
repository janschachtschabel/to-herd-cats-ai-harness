"""Wiki pages (spec 9). Markdown in `content_md` is the only stored form of a page.

`path` is the slugs from the root down, joined by `/`; it is unique in a space among
the pages that are not in the trash, and rewritten for a whole subtree when a page
moves. Pages in the trash keep the path they had, so a restore knows where they were.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk
from app.core.principal import PrincipalType

MAX_DEPTH = 16  # path segments
MAX_CONTENT_CHARS = 200_000
MAX_TITLE_CHARS = 200
MAX_SLUG_CHARS = 80


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
