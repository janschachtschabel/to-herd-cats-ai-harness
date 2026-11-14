"""Skills (spec 11, plan M6 decision 11): instructions in the SKILL.md format that an
agent loads when it needs them.

- `skill`: organisation-wide (`space_id` NULL) or of one space; its `name` is unique
  per organisation and scope (two partial unique indexes); `description` and
  `content` are the current text. `state` is `active` or `archived` (no deletion: an
  archived skill keeps its name and its versions). The author is the principal that
  made it (a person, or later an agent through a proposal).
- `skill_version`: every change of description or content, numbered per skill from
  1 (the creation). Restoring an old one makes a new version.
- `agent_skill`: which skills an agent may use. Whether a run may use one is decided
  at use time (`runs.py`), so a skill whose space the agent left is kept but unused.

Spaces are referenced with `ON DELETE CASCADE`, as everywhere.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk, utcnow
from app.core.principal import PrincipalType
from app.modules.skills.format import MAX_DESCRIPTION_CHARS, MAX_NAME_CHARS


class SkillState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Skill(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "skill"
    __table_args__ = (
        CheckConstraint("state IN ('active', 'archived')", name="state"),
        CheckConstraint("author_type IN ('user', 'agent')", name="author_type"),
        Index(
            "uq_skill_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("space_id IS NULL"),
        ),
        Index(
            "uq_skill_space_name",
            "org_id",
            "space_id",
            "name",
            unique=True,
            postgresql_where=text("space_id IS NOT NULL"),
        ),
        Index("ix_skill_space_id", "space_id"),
    )

    space_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    description: Mapped[str] = mapped_column(String(MAX_DESCRIPTION_CHARS), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[SkillState] = mapped_column(String(16), default=SkillState.ACTIVE, nullable=False)
    author_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SkillVersion(UuidPk, OrgScoped, Base):
    __tablename__ = "skill_version"
    __table_args__ = (
        CheckConstraint("author_type IN ('user', 'agent')", name="author_type"),
        Index("uq_skill_version_skill_id_number", "skill_id", "number", unique=True),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(MAX_DESCRIPTION_CHARS), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AgentSkill(OrgScoped, Base):
    __tablename__ = "agent_skill"
    __table_args__ = (Index("ix_agent_skill_skill_id", "skill_id"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True
    )
