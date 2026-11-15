"""What `/mcp` counts (plan M8 decision 6): one `mcp_call` row per tool call, with
the token, the tool's name (always one of the catalog's), the outcome and how long it
took. Ids, names and numbers only: never arguments or results. The token's person and
the AI administration read them as the token's usage; they go with the token, and
after 90 days (`app/worker/due.py`, MCP_CALL_RETENTION).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow

MAX_TOOL_CHARS = 64


class Outcome(StrEnum):
    OK = "ok"
    REFUSED = "refused"  # the tool answered with an error (not allowed, conflict, refusal)
    INVALID = "invalid"  # the arguments did not fit the tool's model
    FAILED = "failed"  # the tool raised: undone, no detail for the client


class McpCall(UuidPk, OrgScoped, Base):
    __tablename__ = "mcp_call"
    __table_args__ = (
        CheckConstraint(
            f"outcome IN ({', '.join(repr(o.value) for o in Outcome)})", name="outcome"
        ),
        CheckConstraint("duration_ms >= 0", name="duration_ms"),
        Index("ix_mcp_call_token_id_id", "token_id", "id"),
        Index("ix_mcp_call_created_at", "created_at"),  # the due loop's retention
    )

    token_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("access_token.id", ondelete="CASCADE"), nullable=False
    )
    tool: Mapped[str] = mapped_column(String(MAX_TOOL_CHARS), nullable=False)
    outcome: Mapped[Outcome] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
