import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import PageParams


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_type: str
    actor_id: uuid.UUID
    action: str
    target_type: str
    target_id: uuid.UUID
    details: dict[str, Any] | None
    ip: str | None
    created_at: datetime


class AuditQuery(PageParams):
    """`GET /api/admin/audit` filters; both optional."""

    actor_id: uuid.UUID | None = None
    action: str | None = Field(default=None, max_length=64)
