"""Tags (spec 10 "Tags"): one pool per organisation, each tag system-wide
(`space_id` NULL) or belonging to one space, put on objects through `tagging`.

Names are unique case-insensitively within their scope: among the system-wide tags,
and among each space's tags. A space tag goes only on objects of its space.
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk

MAX_TAG_NAME_CHARS = 50


class SubjectType(StrEnum):
    """What can carry tags; widened with each milestone (tickets, skills, agents)."""

    PAGE = "page"


class Tag(UuidPk, OrgScoped, Base):
    __tablename__ = "tag"
    __table_args__ = (
        Index(
            "uq_tag_org_id_name_system",
            "org_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("space_id IS NULL"),
        ),
        Index(
            "uq_tag_space_id_name",
            "space_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("space_id IS NOT NULL"),
        ),
        CheckConstraint("color ~ '^#[0-9a-f]{6}$'", name="color"),
    )

    space_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(MAX_TAG_NAME_CHARS), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)  # `#rrggbb`
    # Bumped by every change of name or colour; a PATCH names the version it read.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Tagging(OrgScoped, Base):
    """A tag on an object. `subject_id` points at a row of the table `subject_type`
    names, so there is no foreign key: whoever deletes the object deletes its rows."""

    __tablename__ = "tagging"
    __table_args__ = (
        CheckConstraint("subject_type IN ('page')", name="subject_type"),
        Index("ix_tagging_subject", "subject_type", "subject_id"),
    )

    tag_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True
    )
    subject_type: Mapped[SubjectType] = mapped_column(String(16), primary_key=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
