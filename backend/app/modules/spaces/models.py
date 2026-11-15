import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.ai.models import AiPolicy, DataLocation

MIN_REVIEW_DAYS = 7
MAX_REVIEW_DAYS = 730
_LOCATIONS = ", ".join(f"'{loc.value}'" for loc in DataLocation)


class SpaceKind(StrEnum):
    OPEN = "open"  # every member reads; guests only by membership
    TEAM = "team"  # members only; invisible to everyone else
    PERSONAL = "personal"  # exactly one person, created with them


class AgentWritePolicy(StrEnum):
    """How agents write pages in a space (plan M6 decision 8)."""

    PROPOSE = "propose"  # through proposals a moderator accepts (the default)
    DIRECT = "direct"  # directly, for agents whose level allows it (`update_page`)


class Space(UuidPk, OrgScoped, Base):
    """Where pages, tickets and channels live; the boundary of every permission."""

    __tablename__ = "space"
    __table_args__ = (
        UniqueConstraint("org_id", "owner_user_id"),
        CheckConstraint("kind IN ('open', 'team', 'personal')", name="kind"),
        CheckConstraint("(kind = 'personal') = (owner_user_id IS NOT NULL)", name="personal_owner"),
        CheckConstraint("ai_policy IN ('any', 'restricted', 'none')", name="ai_policy"),
        CheckConstraint(
            f"allowed_locations <@ ARRAY[{_LOCATIONS}]::varchar[] "
            "AND (ai_policy = 'restricted') = (cardinality(allowed_locations) > 0)",
            name="allowed_locations",
        ),
        CheckConstraint("agent_write_policy IN ('propose', 'direct')", name="agent_write_policy"),
        CheckConstraint(
            f"review_interval_days IS NULL OR review_interval_days BETWEEN "
            f"{MIN_REVIEW_DAYS} AND {MAX_REVIEW_DAYS}",
            name="review_interval_days",
        ),
        Index(
            "ix_space_review_checked_on",
            "review_checked_on",
            postgresql_where=text("review_interval_days IS NOT NULL"),
        ),
    )

    kind: Mapped[SpaceKind] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    icon: Mapped[str | None] = mapped_column(String(32))
    # The person a personal space belongs to; NULL for every other kind.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # What AI may receive of the space's content (spec 7.3, `modules/ai/policy.py`);
    # `allowed_locations` (sorted, no repeats) is set exactly for `restricted`.
    ai_policy: Mapped[AiPolicy] = mapped_column(
        String(16), default=AiPolicy.ANY, server_default=AiPolicy.ANY.value, nullable=False
    )
    allowed_locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), default=list, server_default=text("'{}'::varchar[]"), nullable=False
    )
    # Read by `proposals.service.agent_writes_directly` (the write tools ask it).
    agent_write_policy: Mapped[AgentWritePolicy] = mapped_column(
        String(16),
        default=AgentWritePolicy.PROPOSE,
        server_default=AgentWritePolicy.PROPOSE.value,
        nullable=False,
    )
    # Pages not reviewed for this many days are due (plan M7 decision 11, `wiki/
    # review.py`); NULL: off. Read by the daily pass, the page API and the tree filter.
    review_interval_days: Mapped[int | None] = mapped_column(Integer)
    # The UTC day the daily pass last went through all of the space's due pages
    # (`wiki/review_pass.py`); NULL: not yet, or the interval changed since.
    review_checked_on: Mapped[date | None] = mapped_column(Date)


class SpaceMember(Base):
    """A principal's role in a space. `member_id` points at a person, a group or (M5) an
    agent, so there is no foreign key: deleting a group or an agent removes its rows in
    the same transaction."""

    __tablename__ = "space_member"
    __table_args__ = (
        CheckConstraint("member_type IN ('user', 'group', 'agent')", name="member_type"),
        CheckConstraint("role IN ('viewer', 'editor', 'moderator', 'admin')", name="role"),
        Index("ix_space_member_principal", "member_type", "member_id"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), primary_key=True
    )
    member_type: Mapped[PrincipalType] = mapped_column(String(16), primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    role: Mapped[SpaceRole] = mapped_column(String(16), nullable=False)
