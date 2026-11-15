"""OAuth 2 for connectors (plan M8 decision 9, task 8).

`oauth_client`: the organisation's registration at an authorization server (set up
with `ai.manage`): its endpoints (https, through the egress guard), the `client_id`,
the client secret as a reference (`enc:`/`env:`, absent for a public client, which
relies on PKCE alone), how the secret is presented at the token endpoint
(`token_auth`), the scopes asked for and the `resource` (RFC 8707: the MCP server the
tokens are for). Connectors of kind `oauth` name one; a personal-scope MCP server may
name the one its people connect with.

`oauth_flow`: one authorization in progress. Only the SHA-256 of `state` is kept; the
PKCE verifier is `enc:`; the flow belongs to the login session that started it and
is consumed by the first callback that names it from that session (or expires).
The redirect URI it was started with is sent again at the token endpoint.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk

MAX_NAME_CHARS = 120
MAX_URL_CHARS = 500
MAX_CLIENT_ID_CHARS = 255
MAX_SCOPES_CHARS = 1000


class TokenAuth(StrEnum):
    """How a client secret goes to the token endpoint (RFC 6749 2.3.1)."""

    BASIC = "client_secret_basic"
    POST = "client_secret_post"


class OAuthClient(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "oauth_client"
    __table_args__ = (
        UniqueConstraint("org_id", "name"),
        CheckConstraint(
            "token_auth IN ('client_secret_basic', 'client_secret_post')", name="token_auth"
        ),
        CheckConstraint(
            "client_secret_ref IS NULL OR client_secret_ref LIKE 'enc:%'"
            " OR client_secret_ref LIKE 'env:%'",
            name="client_secret_ref",
        ),
    )

    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    authorization_endpoint: Mapped[str] = mapped_column(String(MAX_URL_CHARS), nullable=False)
    token_endpoint: Mapped[str] = mapped_column(String(MAX_URL_CHARS), nullable=False)
    revocation_endpoint: Mapped[str | None] = mapped_column(String(MAX_URL_CHARS))
    client_id: Mapped[str] = mapped_column(String(MAX_CLIENT_ID_CHARS), nullable=False)
    client_secret_ref: Mapped[str | None] = mapped_column(Text)
    token_auth: Mapped[TokenAuth] = mapped_column(String(32), nullable=False)
    scopes: Mapped[str] = mapped_column(String(MAX_SCOPES_CHARS), nullable=False, default="")
    resource: Mapped[str | None] = mapped_column(String(MAX_URL_CHARS))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OAuthFlow(UuidPk, OrgScoped, Base):
    __tablename__ = "oauth_flow"
    __table_args__ = (CheckConstraint("verifier_ref LIKE 'enc:%'", name="verifier_ref"),)

    connector_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("connector.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_session.id", ondelete="CASCADE"), index=True
    )
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    verifier_ref: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(MAX_URL_CHARS + 100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
