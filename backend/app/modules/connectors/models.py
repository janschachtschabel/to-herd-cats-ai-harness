"""Connectors (plan M8 decision 9): stored credentials for external servers.

- `scope`: `shared` belongs to the organisation (managed with `ai.manage`); `personal`
  belongs to `owner_id` alone (managed by that person, with `ai.use`).
- `auth_kind`: `bearer` sends `Authorization: Bearer <secret>`; `header` sends the
  secret as the value of `header_name`; `oauth` (task 8) sends the access token it
  got from the authorization server of its `oauth_client_id` as a bearer token.
- `secret_ref` is a reference (`core/secrets.py`), never the secret: `enc:` or, for a
  shared connector, `env:HERD_AI_*`; a personal one is `enc:` only (a person cannot
  name the server's environment). For `oauth` it is the access token, `enc:` only,
  and NULL while the connector is not connected; `refresh_token_ref` (`enc:`) and
  `token_expires_at` come with it and go with it.
- `mcp_server_id` (personal only, task 6): the external MCP server a personal
  connector serves, at most one per person and server; it goes with the server.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk

MAX_NAME_CHARS = 120
MAX_HEADER_CHARS = 100


class ConnectorScope(StrEnum):
    SHARED = "shared"
    PERSONAL = "personal"


class AuthKind(StrEnum):
    BEARER = "bearer"
    HEADER = "header"
    OAUTH = "oauth"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class Connector(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "connector"
    __table_args__ = (
        CheckConstraint(_in("scope", ConnectorScope), name="scope"),
        CheckConstraint(_in("auth_kind", AuthKind), name="auth_kind"),
        CheckConstraint("(scope = 'personal') = (owner_id IS NOT NULL)", name="owner"),
        CheckConstraint("(auth_kind = 'header') = (header_name IS NOT NULL)", name="header_name"),
        CheckConstraint(
            "secret_ref LIKE 'enc:%' OR (scope = 'shared' AND secret_ref LIKE 'env:%')",
            name="secret_ref",
        ),
        CheckConstraint("(auth_kind = 'oauth') = (oauth_client_id IS NOT NULL)", name="oauth"),
        CheckConstraint("auth_kind = 'oauth' OR secret_ref IS NOT NULL", name="secret_set"),
        CheckConstraint(
            "auth_kind <> 'oauth' OR secret_ref IS NULL OR secret_ref LIKE 'enc:%'",
            name="oauth_secret",
        ),
        CheckConstraint(
            "refresh_token_ref IS NULL OR (secret_ref IS NOT NULL"
            " AND refresh_token_ref LIKE 'enc:%')",
            name="refresh_token",
        ),
        CheckConstraint("auth_kind = 'oauth' OR token_expires_at IS NULL", name="token_expires"),
        # One name per owner (the service also compares case-insensitively).
        Index(
            "uq_connector_shared_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("owner_id IS NULL"),
        ),
        Index(
            "uq_connector_personal_name",
            "owner_id",
            "name",
            unique=True,
            postgresql_where=text("owner_id IS NOT NULL"),
        ),
        CheckConstraint("mcp_server_id IS NULL OR scope = 'personal'", name="server"),
        Index(
            "uq_connector_server_owner",
            "mcp_server_id",
            "owner_id",
            unique=True,
            postgresql_where=text("mcp_server_id IS NOT NULL"),
        ),
    )

    scope: Mapped[ConnectorScope] = mapped_column(String(16), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    auth_kind: Mapped[AuthKind] = mapped_column(String(16), nullable=False)
    header_name: Mapped[str | None] = mapped_column(String(MAX_HEADER_CHARS))
    secret_ref: Mapped[str | None] = mapped_column(Text)
    oauth_client_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("oauth_client.id", ondelete="RESTRICT"), index=True
    )
    refresh_token_ref: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.id", ondelete="CASCADE", use_alter=True),
    )
    # Bumped by every write; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
