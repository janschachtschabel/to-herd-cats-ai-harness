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


class ConnectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    auth_kind: AuthKind
    header_name: HeaderName | None = None
    secret: SecretIn

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _check_header(self.header_name)
        check_auth(self.auth_kind, self.header_name)
        return self


class ConnectorUpdate(BaseModel):
    """Only the fields sent change; `secret` replaces the stored one."""

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
    has_secret: bool
    secret_kind: SecretKind
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
            has_secret=True,
            secret_kind=kind_of(connector.secret_ref),
            version=connector.version,
            created_at=connector.created_at,
            updated_at=connector.updated_at,
        )
