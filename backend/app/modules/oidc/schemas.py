"""OIDC providers and linked accounts as the API takes and shows them. The client
secret is written, never shown: the answer says only whether one is set and which
kind of reference it is."""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, model_validator

from app.core.secrets import SecretKind, kind_of
from app.modules.oidc.models import (
    MAX_CLIENT_ID_CHARS,
    MAX_DOMAIN_CHARS,
    MAX_DOMAINS,
    MAX_NAME_CHARS,
    MAX_SCOPES_CHARS,
    MAX_URL_CHARS,
    OidcProvider,
    ProviderKind,
    UserIdentity,
)

Key = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_URL_CHARS)
]
ClientId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_CLIENT_ID_CHARS, pattern=r"^[ -~]+$"
    ),
]
Scopes = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=MAX_SCOPES_CHARS,
        pattern=r"^[\x21\x23-\x5b\x5d-\x7e]+( [\x21\x23-\x5b\x5d-\x7e]+)*$",
    ),
]
Domain = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_DOMAIN_CHARS)]
Domains = Annotated[list[Domain], Field(max_length=MAX_DOMAINS)]


class OidcSecretIn(BaseModel):
    """Either the secret itself (`value`, stored encrypted; needs `HERD_SECRET_KEY`) or
    the name of an environment variable `HERD_OIDC_*` (`env`)."""

    model_config = ConfigDict(extra="forbid")

    value: SecretStr | None = None
    env: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.value is None) == (self.env is None):
            raise ValueError("give either value or env")
        return self


class ProviderCreate(BaseModel):
    """`google`: issuer and scopes are the preset's (`issuer`, `scopes`, `trust_email`
    are refused); `generic`: `issuer` is required, `scopes` must hold `openid`."""

    model_config = ConfigDict(extra="forbid")

    kind: ProviderKind
    key: Key | None = None
    name: Name | None = None
    issuer: Url | None = None
    client_id: ClientId
    client_secret: OidcSecretIn | None = None
    scopes: Scopes | None = None
    trust_email: bool = False
    allow_signup: bool = False
    allowed_domains: Domains = []
    enabled: bool = False


class ProviderUpdate(BaseModel):
    """Only the fields sent change; `client_secret` replaces the stored one."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: Name | None = None
    issuer: Url | None = None
    client_id: ClientId | None = None
    client_secret: OidcSecretIn | None = None
    scopes: Scopes | None = None
    trust_email: bool | None = None
    allow_signup: bool | None = None
    allowed_domains: Domains | None = None
    enabled: bool | None = None


class SecretState(BaseModel):
    set: bool
    kind: SecretKind | None


class ProviderOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    kind: ProviderKind
    issuer: str
    client_id: str
    client_secret: SecretState
    scopes: str
    trust_email: bool
    allow_signup: bool
    allowed_domains: list[str]
    enabled: bool
    discovered: bool
    callback_url: str | None
    version: int

    @classmethod
    def of(cls, provider: OidcProvider, callback_url: str | None) -> "ProviderOut":
        ref = provider.client_secret_ref
        return cls(
            id=provider.id,
            key=provider.key,
            name=provider.name,
            kind=ProviderKind(provider.kind),
            issuer=provider.issuer,
            client_id=provider.client_id,
            client_secret=SecretState(set=ref is not None, kind=kind_of(ref) if ref else None),
            scopes=provider.scopes,
            trust_email=provider.trust_email,
            allow_signup=provider.allow_signup,
            allowed_domains=list(provider.allowed_domains),
            enabled=provider.enabled,
            discovered=provider.token_endpoint is not None,
            callback_url=callback_url,
            version=provider.version,
        )


class ProviderCheckOut(BaseModel):
    """`code` is None when discovery and the JWKS answered as OIDC promises."""

    ok: bool
    code: str | None


class PublicProviderOut(BaseModel):
    key: str
    name: str
    kind: ProviderKind


class IdentityOut(BaseModel):
    id: uuid.UUID
    provider_key: str
    provider_name: str
    provider_kind: ProviderKind
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def of(cls, identity: UserIdentity, provider: OidcProvider) -> "IdentityOut":
        return cls(
            id=identity.id,
            provider_key=provider.key,
            provider_name=provider.name,
            provider_kind=ProviderKind(provider.kind),
            created_at=identity.created_at,
            last_login_at=identity.last_login_at,
        )


class LinkStartOut(BaseModel):
    """Where the browser goes to link an account (the provider's sign-in page)."""

    url: str
