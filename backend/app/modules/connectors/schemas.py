"""Connectors as the API takes and shows them. A secret is written, never shown: the
answer says only that one is set and which kind of reference it is."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.core.secrets import SecretKind, kind_of
from app.modules.ai.schemas import SecretIn
from app.modules.connectors.models import (
    MAX_HEADER_CHARS,
    MAX_NAME_CHARS,
    AuthKind,
    Connector,
    ConnectorScope,
)

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
]
# An HTTP header name (RFC 9110 token).
HeaderName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=MAX_HEADER_CHARS, pattern=r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$"
    ),
]
# Headers the HTTP client or the MCP protocol set themselves; a connector may not.
RESERVED_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "content-type",
        "content-encoding",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "upgrade",
        "te",
        "trailer",
        "accept",
        "accept-encoding",
        "proxy-authorization",
        "mcp-session-id",
        "mcp-protocol-version",
        "last-event-id",
    }
)
_RESERVED_PREFIX = re.compile(r"^(proxy-|sec-)", re.IGNORECASE)


def _check_header(name: str | None) -> str | None:
    if name is not None and (name.lower() in RESERVED_HEADERS or _RESERVED_PREFIX.match(name)):
        raise ValueError("this header is set by the client itself")
    return name


def check_auth(kind: AuthKind, header_name: str | None) -> None:
    """A `header` connector names its header; a `bearer` one has none."""
    if (kind == AuthKind.HEADER) != (header_name is not None):
        raise ValueError("header_name is needed for auth_kind header, and only for it")


def check_secret(
    kind: AuthKind, secret: SecretIn | None, oauth_client_id: uuid.UUID | None
) -> None:
    """An `oauth` connector names its OAuth client and gets its secret (the tokens) by
    being connected; the other kinds take a secret and no client."""
    oauth = kind == AuthKind.OAUTH
    if oauth != (oauth_client_id is not None):
        raise ValueError("oauth_client_id is needed for auth_kind oauth, and only for it")
    if oauth == (secret is not None):
        raise ValueError("a secret is needed for auth_kind bearer and header, never for oauth")


class ConnectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    auth_kind: AuthKind
    header_name: HeaderName | None = None
    # `bearer`, `header`: required; `oauth`: none (the tokens come by connecting).
    secret: SecretIn | None = None
    # `oauth` only: the organisation's OAuth client it connects with (plan M8 task 8).
    oauth_client_id: uuid.UUID | None = None
    # Personal connectors only: the external MCP server it serves (plan M8 task 6).
    mcp_server_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _check_header(self.header_name)
        check_auth(self.auth_kind, self.header_name)
        check_secret(self.auth_kind, self.secret, self.oauth_client_id)
        return self


class ConnectorUpdate(BaseModel):
    """Only the fields sent change; `secret` replaces the stored one. An `oauth`
    connector stays one (its tokens change by connecting and disconnecting), and no
    other connector becomes one."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: Name | None = None
    auth_kind: AuthKind | None = None
    header_name: HeaderName | None = None
    secret: SecretIn | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _check_header(self.header_name)
        for field in ("name", "auth_kind", "secret"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be removed")
        return self


class ConnectorOut(BaseModel):
    id: uuid.UUID
    name: str
    scope: ConnectorScope
    auth_kind: AuthKind
    header_name: str | None
    oauth_client_id: uuid.UUID | None
    mcp_server_id: uuid.UUID | None
    # For `oauth`: whether it is connected (has tokens).
    has_secret: bool
    secret_kind: SecretKind | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, connector: Connector) -> "ConnectorOut":
        return cls(
            id=connector.id,
            name=connector.name,
            scope=connector.scope,
            auth_kind=connector.auth_kind,
            header_name=connector.header_name,
            oauth_client_id=connector.oauth_client_id,
            mcp_server_id=connector.mcp_server_id,
            has_secret=connector.secret_ref is not None,
            secret_kind=kind_of(connector.secret_ref) if connector.secret_ref else None,
            version=connector.version,
            created_at=connector.created_at,
            updated_at=connector.updated_at,
        )


class VersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
