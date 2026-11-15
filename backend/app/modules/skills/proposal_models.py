"""Skill proposals (plan M6 decision 11, task 9): a new skill or a change to one,
made by an agent's run (`propose_skill`, level 2), decided by whoever may manage
skills in its scope (`page.moderate` in its space, or `skill.manage`).

- `change`: `skill_id` is the skill; `base_number` is the number of its newest
  version when the proposal was made. Accepting it while the skill has a newer
  version answers 409 with both texts; the moderator accepts again with the final
  text. `name` is NULL (a proposal changes text, never the name).
- `new`: `name` is the new skill's name in the scope (`space_id`, NULL:
  organisation-wide); `skill_id` is set when it is accepted (the skill it became).
- `description` and `content` are the proposed text, `reason` why (≤ 300).
- The author is a principal (an agent whose run made it, `run_id`, no foreign key
  like `page_proposal.run_id`; a person through the service). A decision names who
  decided, when, a rejection's optional reason, and an acceptance's skill version
  (`result_version_id`; NULL when the skill already held that text).

Spaces and skills are referenced with `ON DELETE CASCADE`.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.core.principal import PrincipalType
from app.modules.skills.format import MAX_DESCRIPTION_CHARS, MAX_NAME_CHARS

MAX_REASON_CHARS = 300


class SkillProposalKind(StrEnum):
    CHANGE = "change"
    NEW = "new"


class SkillProposalState(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class SkillProposal(UuidPk, OrgScoped, Base):
    __tablename__ = "skill_proposal"
    __table_args__ = (
        CheckConstraint(_in("kind", SkillProposalKind), name="kind"),
        CheckConstraint(_in("state", SkillProposalState), name="state"),
        CheckConstraint("author_type IN ('user', 'agent')", name="author_type"),
        CheckConstraint(
            "(kind = 'change' AND skill_id IS NOT NULL AND name IS NULL"
            " AND base_number IS NOT NULL)"
            " OR (kind = 'new' AND name IS NOT NULL AND base_number IS NULL"
            " AND (skill_id IS NULL OR state = 'accepted'))",
            name="shape",
        ),
        CheckConstraint(
            "(state = 'open') = (decided_at IS NULL)"
            " AND (state = 'rejected' OR decision_reason IS NULL)",
            name="decision",
        ),
        Index("ix_skill_proposal_space_id", "space_id"),
        Index("ix_skill_proposal_skill_id", "skill_id"),
        Index("ix_skill_proposal_result_version_id", "result_version_id"),
    )

    space_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE")
    )
    kind: Mapped[SkillProposalKind] = mapped_column(String(16), nullable=False)
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill.id", ondelete="CASCADE")
    )
    name: Mapped[str | None] = mapped_column(String(MAX_NAME_CHARS))
    base_number: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(MAX_DESCRIPTION_CHARS), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(MAX_REASON_CHARS), nullable=False)
    author_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    state: Mapped[SkillProposalState] = mapped_column(
        String(16), default=SkillProposalState.OPEN, nullable=False
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(MAX_REASON_CHARS))
    result_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill_version.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
