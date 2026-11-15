"""External MCP servers and their tools as the API takes and shows them."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.mcp.client import RemoteStatus
from app.modules.ai.models import DataLocation
from app.modules.mcp_servers.listing import problem_of
from app.modules.mcp_servers.models import (
    MAX_NAME_CHARS,
    MAX_URL_CHARS,
    Classification,
    ConnectorUse,
    McpServer,
    McpServerTool,
    ToolState,
)
from app.modules.mcp_servers.schema_view import SchemaProblem

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_URL_CHARS)
]


def check_connector(scope: ConnectorUse | None, connector_id: uuid.UUID | None) -> None:
    if (scope == ConnectorUse.SHARED) != (connector_id is not None):
        raise ValueError("connector_id is needed for connector_scope shared, and only for it")


def check_oauth_client(scope: ConnectorUse | None, oauth_client_id: uuid.UUID | None) -> None:
    if oauth_client_id is not None and scope != ConnectorUse.PERSONAL:
        raise ValueError("oauth_client_id goes only with connector_scope personal")


class ServerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    url: Url
    data_location: DataLocation = DataLocation.EXTERNAL
    connector_scope: ConnectorUse = ConnectorUse.NONE
    connector_id: uuid.UUID | None = None
    # `personal` only: the OAuth client people connect their own connector with.
    oauth_client_id: uuid.UUID | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def _shape(self) -> Self:
        check_connector(self.connector_scope, self.connector_id)
        check_oauth_client(self.connector_scope, self.oauth_client_id)
        return self


class ServerUpdate(BaseModel):
    """Only the fields sent change. A new URL withdraws every approval; a new origin
    also disconnects every personal connector of the server and detaches its shared
    connector, unless `keep_shared_connector` says to keep it or the change names
    another shared connector (`connectors/moving.py`)."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: Name | None = None
    url: Url | None = None
    data_location: DataLocation | None = None
    connector_scope: ConnectorUse | None = None
    connector_id: uuid.UUID | None = None
    oauth_client_id: uuid.UUID | None = None
    enabled: bool | None = None
    keep_shared_connector: bool = False

    @model_validator(mode="after")
    def _shape(self) -> Self:
        for field in ("name", "url", "data_location", "connector_scope", "enabled"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be removed")
        return self


class RefreshOut(BaseModel):
    """How reading the tool list went: counts of tools new, with another fingerprint
    and no longer listed; all 0 unless `status` is `ok`."""

    status: RemoteStatus
    new: int = 0
    changed: int = 0
    missing: int = 0


class ServerOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    data_location: DataLocation
    connector_scope: ConnectorUse
    connector_id: uuid.UUID | None
    oauth_client_id: uuid.UUID | None
    # The catalogue entry it was created from, if any.
    catalog_id: str | None
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, server: McpServer) -> "ServerOut":
        return cls(
            id=server.id,
            name=server.name,
            url=server.url,
            data_location=server.data_location,
            connector_scope=server.connector_scope,
            connector_id=server.connector_id,
            oauth_client_id=server.oauth_client_id,
            catalog_id=server.catalog_id,
            enabled=server.enabled,
            version=server.version,
            created_at=server.created_at,
            updated_at=server.updated_at,
        )


class CreatedServerOut(ServerOut):
    refresh: RefreshOut


class TestOut(BaseModel):
    status: RemoteStatus
    tools: int | None
    duration_ms: int


class PersonalServerOut(BaseModel):
    """A server that acts with each person's own connector, and whether the caller
    has connected theirs."""

    id: uuid.UUID
    name: str
    # Where the person's own secret goes once connected (a new origin disconnects it).
    url: str
    connected: bool
    # The OAuth client to connect with (create an `oauth` connector naming it), if any.
    oauth_client_id: uuid.UUID | None


class ToolOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only_hint: bool
    fingerprint: str
    approved_fingerprint: str | None
    classification: Classification
    # What the server's catalogue entry suggests, if it was created from one and the
    # entry knows the tool; a suggestion, never an approval.
    suggested_classification: Classification | None
    state: ToolState
    missing: bool
    # Why its input schema cannot be offered to a model (then it cannot be approved):
    # `schema_too_large` (over 64 KiB, or too large to offer), `schema_unsupported`.
    schema_problem: SchemaProblem | None
    version: int
    updated_at: datetime

    @classmethod
    def of(cls, tool: McpServerTool, suggested: Classification | None = None) -> "ToolOut":
        return cls(
            id=tool.id,
            server_id=tool.server_id,
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            read_only_hint=tool.read_only_hint,
            fingerprint=tool.fingerprint,
            approved_fingerprint=tool.approved_fingerprint,
            classification=tool.classification,
            suggested_classification=suggested,
            state=tool.state,
            missing=tool.missing,
            schema_problem=problem_of(tool),
            version=tool.version,
            updated_at=tool.updated_at,
        )


class ToolVersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


class ToolClassify(BaseModel):
    """`read` for a tool the server does not annotate read-only loosens what the admin
    was offered: it needs `confirm_loosen`."""

    model_config = ConfigDict(extra="forbid")

    version: int
    classification: Classification
    confirm_loosen: bool = False
