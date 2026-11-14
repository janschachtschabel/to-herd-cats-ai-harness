"""Page proposals (spec 9, plan M6 decision 8): a change to an existing page or a new
page, made by someone who does not write it directly (an agent at level 2, or a
space whose `agent_write_policy` is `propose`), decided by a moderator.

- `change`: `page_id` is the page; `base_version` and `base_content_md` are its
  newest version's number and the page's content when the proposal was made. The
  content is kept, not only the number: a live session may still fold saves into
  that version afterwards, and the merge needs the text the proposal started from.
- `new`: `parent_id` is the page it goes under (NULL: the top level) and `title` its
  title; `page_id` is set when it is accepted (the page it became).
- The author is a principal (a person, or an agent whose run made it, `run_id`; no
  foreign key, like `usage_record.run_id`: a proposal outlives its run). A decision
  names who decided (`decided_by_id`, a person), when, and for a rejection an
  optional reason; an accepted proposal names the version it produced.

Pages and versions are referenced with `ON DELETE CASCADE`: purging a page from the
trash takes its proposals with it.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.core.principal import PrincipalType
from app.modules.wiki.models import MAX_SUMMARY_CHARS, MAX_TITLE_CHARS

MAX_REASON_CHARS = MAX_SUMMARY_CHARS  # the reason becomes the version's change text


class ProposalKind(StrEnum):
    CHANGE = "change"
    NEW = "new"


class ProposalState(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class PageProposal(UuidPk, OrgScoped, Base):
    __tablename__ = "page_proposal"
    __table_args__ = (
        CheckConstraint(_in("kind", ProposalKind), name="kind"),
        CheckConstraint(_in("state", ProposalState), name="state"),
        CheckConstraint("author_type IN ('user', 'agent')", name="author_type"),
        CheckConstraint(
            "(kind = 'change' AND page_id IS NOT NULL AND parent_id IS NULL AND title IS NULL"
            " AND base_version IS NOT NULL AND base_content_md IS NOT NULL)"
            " OR (kind = 'new' AND title IS NOT NULL AND base_version IS NULL"
            " AND base_content_md IS NULL AND (page_id IS NULL OR state = 'accepted'))",
            name="shape",
        ),
        CheckConstraint(
            "(state = 'open') = (decided_at IS NULL)"
            " AND (state = 'rejected' OR decision_reason IS NULL)",
            name="decision",
        ),
        Index("ix_page_proposal_space_id_id", "space_id", "id"),
        Index("ix_page_proposal_page_id", "page_id"),
        Index("ix_page_proposal_parent_id", "parent_id"),
        Index("ix_page_proposal_result_version_id", "result_version_id"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ProposalKind] = mapped_column(String(16), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE")
    )
    title: Mapped[str | None] = mapped_column(String(MAX_TITLE_CHARS))
    base_version: Mapped[int | None] = mapped_column(Integer)
    base_content_md: Mapped[str | None] = mapped_column(Text)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(MAX_REASON_CHARS), nullable=False)
    author_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    state: Mapped[ProposalState] = mapped_column(
        String(16), default=ProposalState.OPEN, nullable=False
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(MAX_REASON_CHARS))
    result_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page_version.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
