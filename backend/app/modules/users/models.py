from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.core.principal import SystemRole


class User(UuidPk, OrgScoped, Base):
    """A person. `app_user`, because `user` is a reserved word in PostgreSQL."""

    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("org_id", "email"),
        # Awaiting approval is a kind of inactive: every "active only" filter keeps the
        # person out without knowing about approvals.
        CheckConstraint(
            "awaiting_approval_since IS NULL OR NOT is_active", name="awaiting_inactive"
        ),
        Index(
            "ix_app_user_org_id_awaiting",
            "org_id",
            "id",
            postgresql_where=text("awaiting_approval_since IS NOT NULL"),
        ),
    )

    email: Mapped[str] = mapped_column(String(254), nullable=False)  # stored lower-case
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    system_role: Mapped[SystemRole] = mapped_column(
        String(16), default=SystemRole.MEMBER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="de", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Self-registered through OIDC and not yet approved or rejected by an admin (Jan's
    # answer J2: nobody gets in without approval); always with `is_active` false.
    awaiting_approval_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped by every administrative change; a PATCH names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
