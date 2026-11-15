"""External MCP servers and their tools (plan M8 decision 7).

`mcp_server`: an endpoint (Streamable HTTP over https), the `data_location` its calls
send data to (as for an AI connection; the policy uses it in task 7), and which
credential it uses: `none`, `shared` (one shared connector, `connector_id`) or
`personal` (each person's own connector bound to this server, `connector.mcp_server_id`;
`oauth_client_id` names the OAuth client people connect it with, if any).

`mcp_server_tool`: one tool as the server listed it. `fingerprint` is the SHA-256 over
name, description and input schema as last read; `approved_fingerprint` the one an
admin approved. Only `state = approved` with both equal and the tool still listed may
be called; a refresh that reads another fingerprint sets an approved tool `changed`.
`classification` (`read`/`write`) is the admin's; the proposal is `read` only when the
server annotates the tool read-only (`read_only_hint`).
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk
from app.modules.ai.models import DataLocation

MAX_NAME_CHARS = 120
MAX_URL_CHARS = 500
MAX_TOOL_NAME_CHARS = 128
MAX_DESCRIPTION_CHARS = 10_000


class ConnectorUse(StrEnum):
    NONE = "none"
    SHARED = "shared"
    PERSONAL = "personal"


class Classification(StrEnum):
    READ = "read"
    WRITE = "write"


class ToolState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"
    CHANGED = "changed"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class McpServer(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "mcp_server"
    __table_args__ = (
        UniqueConstraint("org_id", "name"),
        CheckConstraint(_in("data_location", DataLocation), name="data_location"),
        CheckConstraint(_in("connector_scope", ConnectorUse), name="connector_scope"),
        CheckConstraint(
            "(connector_scope = 'shared') = (connector_id IS NOT NULL)", name="connector"
        ),
        CheckConstraint(
            "oauth_client_id IS NULL OR connector_scope = 'personal'", name="oauth_client"
        ),
    )

    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    url: Mapped[str] = mapped_column(String(MAX_URL_CHARS), nullable=False)
    data_location: Mapped[DataLocation] = mapped_column(String(16), nullable=False)
    connector_scope: Mapped[ConnectorUse] = mapped_column(String(16), nullable=False)
    connector_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("connector.id", ondelete="RESTRICT"), index=True
    )
    # Personal scope only: the OAuth client people connect their own connector with.
    oauth_client_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("oauth_client.id", ondelete="RESTRICT"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Bumped by every write; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class McpServerTool(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "mcp_server_tool"
    __table_args__ = (
        UniqueConstraint("server_id", "name"),
        CheckConstraint(_in("classification", Classification), name="classification"),
        CheckConstraint(_in("state", ToolState), name="state"),
        CheckConstraint("state <> 'approved' OR approved_fingerprint IS NOT NULL", name="approved"),
        Index("ix_mcp_server_tool_server_id_id", "server_id", "id"),
    )

    server_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("mcp_server.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(MAX_TOOL_NAME_CHARS), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    read_only_hint: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_fingerprint: Mapped[str | None] = mapped_column(String(64))
    classification: Mapped[Classification] = mapped_column(String(16), nullable=False)
    state: Mapped[ToolState] = mapped_column(String(16), nullable=False)
    # The server no longer lists it (a later refresh that lists it again clears it).
    missing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
