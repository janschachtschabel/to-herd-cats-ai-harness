"""Sign-in through OpenID Connect (plan M9 decisions 12 to 15).

`oidc_provider`: an identity provider of the organisation (managed with
`user.manage`). `key` names it in URLs (`/api/auth/oidc/<key>/start`); `kind` is
`google` (the preset: fixed issuer and scopes, Google's own rule for which addresses
it is authoritative) or `generic`. The client secret is a reference (`enc:` or
`env:HERD_OIDC_*`), never shown. Discovery fills the three endpoints; the JWKS is kept
with the time it was fetched (an unknown `kid` fetches it again at most once a
minute). `trust_email`: a generic provider is authoritative for every verified
address it reports (off by default). Self-registration (`allow_signup`) works only
with a non-empty `allowed_domains` (lower case, no trailing dot, exact).

`oidc_flow`: one sign-in in progress, for ten minutes. Only the SHA-256 of `state`
and of the browser binding (the `herd_oidc` cookie) are kept; `nonce` and the PKCE
verifier are one-time values. `link_session_id`: a flow started from the profile to
link an account to the person of that login session.

`user_identity`: a person's account at a provider, by the provider's `sub`.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk, utcnow

MAX_KEY_CHARS = 40
MAX_NAME_CHARS = 120
MAX_URL_CHARS = 500
MAX_CLIENT_ID_CHARS = 255
MAX_SCOPES_CHARS = 500
MAX_SUBJECT_CHARS = 255
MAX_DOMAINS = 50
MAX_DOMAIN_CHARS = 253


class ProviderKind(StrEnum):
    GOOGLE = "google"
    GENERIC = "generic"


class OidcProvider(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "oidc_provider"
    __table_args__ = (
        UniqueConstraint("org_id", "key"),
        CheckConstraint("kind IN ('google', 'generic')", name="kind"),
        CheckConstraint(
            "client_secret_ref IS NULL OR client_secret_ref LIKE 'enc:%'"
            " OR client_secret_ref LIKE 'env:%'",
            name="client_secret_ref",
        ),
    )

    key: Mapped[str] = mapped_column(String(MAX_KEY_CHARS), nullable=False)
    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    kind: Mapped[ProviderKind] = mapped_column(String(16), nullable=False)
    issuer: Mapped[str] = mapped_column(String(MAX_URL_CHARS), nullable=False)
    client_id: Mapped[str] = mapped_column(String(MAX_CLIENT_ID_CHARS), nullable=False)
    client_secret_ref: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(String(MAX_SCOPES_CHARS), nullable=False)
    trust_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_signup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_domains: Mapped[list[str]] = mapped_column(
        ARRAY(String(MAX_DOMAIN_CHARS)), nullable=False, default=list
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authorization_endpoint: Mapped[str | None] = mapped_column(String(MAX_URL_CHARS))
    token_endpoint: Mapped[str | None] = mapped_column(String(MAX_URL_CHARS))
    jwks_uri: Mapped[str | None] = mapped_column(String(MAX_URL_CHARS))
    jwks: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    jwks_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OidcFlow(UuidPk, OrgScoped, Base):
    __tablename__ = "oidc_flow"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("oidc_provider.id", ondelete="CASCADE"), index=True
    )
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    link_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_session.id", ondelete="CASCADE"), index=True
    )
    # A sign-in meant as the proof before linking (`prompt=login`, R18-10): only such a
    # one, freshly made at the provider, opens a session that counts as re-authenticated.
    reauth: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )


class UserIdentity(UuidPk, OrgScoped, Base):
    __tablename__ = "user_identity"
    __table_args__ = (UniqueConstraint("provider_id", "subject"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("oidc_provider.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(MAX_SUBJECT_CHARS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
