import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow

ADMIN_ACCESS = "space.admin_access"
AGENT_ADMIN_ACCESS = "agent.admin_access"  # someone else's personal agent (plan M6)
# A private calendar event's content read by admin power alone (plan M10, R3a-4).
CALENDAR_PRIVATE_READ = "calendar.private_read"
# A calendar event changed or deleted by admin power alone (plan M10, task 3b): every
# write, ids and field names only.
CALENDAR_ADMIN_WRITE = "calendar.admin_write"


class AuditLog(UuidPk, OrgScoped, Base):
    """Who did what to which object, written in the transaction of the change. Rows are
    only ever added (the repository offers nothing else)."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_org_id_created_at", "org_id", "created_at", "id"),
        # At most one admin-access entry per admin, space and UTC day.
        Index(
            "uq_audit_log_admin_access_daily",
            "actor_id",
            "target_id",
            text("((created_at AT TIME ZONE 'UTC')::date)"),
            unique=True,
            postgresql_where=text(f"action = '{ADMIN_ACCESS}'"),
        ),
        # At most one entry per admin, personal agent of someone else and UTC day.
        Index(
            "uq_audit_log_agent_admin_access_daily",
            "actor_id",
            "target_id",
            text("((created_at AT TIME ZONE 'UTC')::date)"),
            unique=True,
            postgresql_where=text(f"action = '{AGENT_ADMIN_ACCESS}'"),
        ),
        # At most one entry per admin, private calendar event and UTC day.
        Index(
            "uq_audit_log_calendar_private_read_daily",
            "actor_id",
            "target_id",
            text("((created_at AT TIME ZONE 'UTC')::date)"),
            unique=True,
            postgresql_where=text(f"action = '{CALENDAR_PRIVATE_READ}'"),
        ),
    )

    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))  # the client address, if any
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
