import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.core.principal import PrincipalType


class Group(UuidPk, OrgScoped, Base):
    """A named set of principals; it can be a member of spaces. `user_group`, because
    `group` is a reserved word in SQL."""

    __tablename__ = "user_group"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    # Bumped by every change of name or description; a PATCH names the version it read.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class GroupMember(Base):
    """A principal in a group. People only in M1; agents join in M6 (widen the CHECK)."""

    __tablename__ = "group_member"
    __table_args__ = (
        CheckConstraint("member_type IN ('user')", name="member_type"),
        Index("ix_group_member_principal", "member_type", "member_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_group.id", ondelete="CASCADE"), primary_key=True
    )
    member_type: Mapped[PrincipalType] = mapped_column(String(16), primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
