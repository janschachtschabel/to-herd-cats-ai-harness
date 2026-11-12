import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType


class SpaceKind(StrEnum):
    OPEN = "open"  # every member reads; guests only by membership
    TEAM = "team"  # members only; invisible to everyone else
    PERSONAL = "personal"  # exactly one person, created with them


class Space(UuidPk, OrgScoped, Base):
    """Where pages, tickets and channels live; the boundary of every permission."""

    __tablename__ = "space"
    __table_args__ = (
        UniqueConstraint("org_id", "slug"),
        UniqueConstraint("org_id", "owner_user_id"),
        CheckConstraint("kind IN ('open', 'team', 'personal')", name="kind"),
        CheckConstraint("(kind = 'personal') = (owner_user_id IS NOT NULL)", name="personal_owner"),
    )

    kind: Mapped[SpaceKind] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)  # stays when renamed
    description: Mapped[str | None] = mapped_column(String(1000))
    icon: Mapped[str | None] = mapped_column(String(32))
    # The person a personal space belongs to; NULL for every other kind.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SpaceMember(Base):
    """A principal's role in a space. `member_id` points at a person or a group, so there
    is no foreign key: deleting a group removes its rows in the same transaction."""

    __tablename__ = "space_member"
    __table_args__ = (
        CheckConstraint("member_type IN ('user', 'group')", name="member_type"),
        CheckConstraint("role IN ('viewer', 'editor', 'moderator', 'admin')", name="role"),
        Index("ix_space_member_principal", "member_type", "member_id"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), primary_key=True
    )
    member_type: Mapped[PrincipalType] = mapped_column(String(16), primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    role: Mapped[SpaceRole] = mapped_column(String(16), nullable=False)
