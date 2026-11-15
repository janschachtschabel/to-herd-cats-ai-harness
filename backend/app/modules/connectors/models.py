"""Connectors (plan M8 decision 9): stored credentials for external servers.

- `scope`: `shared` belongs to the organisation (managed with `ai.manage`); `personal`
  belongs to `owner_id` alone (managed by that person, with `ai.use`).
- `auth_kind`: `bearer` sends `Authorization: Bearer <secret>`; `header` sends the
  secret as the value of `header_name`. OAuth (task 8) adds a kind and its columns.
- `secret_ref` is a reference (`core/secrets.py`), never the secret: `enc:` or, for a
  shared connector, `env:HERD_AI_*`; a personal one is `enc:` only (a person cannot
  name the server's environment).
- `mcp_server_id` (personal only, task 6): the external MCP server a personal
  connector serves, at most one per person and server; it goes with the server.
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
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
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_server.id", ondelete="CASCADE", use_alter=True),
    )
    # Bumped by every write; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
