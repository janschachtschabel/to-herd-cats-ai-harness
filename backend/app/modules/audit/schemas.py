import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.pagination import PageParams
from app.modules.audit.repository import NamedEntry


class AuditOut(BaseModel):
    """`actor_name`: the acting person's display name (None for other principals)."""

    id: uuid.UUID
    actor_type: str
    actor_id: uuid.UUID
    actor_name: str | None
    action: str
    target_type: str
    target_id: uuid.UUID
    details: dict[str, Any] | None
    ip: str | None
    created_at: datetime

    @classmethod
    def of(cls, row: NamedEntry) -> "AuditOut":
        e = row.entry
        return cls(
            id=e.id,
            actor_type=e.actor_type,
            actor_id=e.actor_id,
            actor_name=row.actor_name,
            action=e.action,
            target_type=e.target_type,
            target_id=e.target_id,
            details=e.details,
            ip=e.ip,
            created_at=e.created_at,
        )


class AuditQuery(PageParams):
    """`GET /api/admin/audit` filters; both optional."""

    actor_id: uuid.UUID | None = None
    action: str | None = Field(default=None, max_length=64)
