"""OAuth clients as the API takes and shows them. The client secret is written, never
shown: the answer says only whether one is set and which kind of reference it is."""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.core.secrets import SecretKind, kind_of
from app.modules.ai.schemas import SecretIn
from app.modules.oauth.discovery import DiscoveryStatus
from app.modules.oauth.models import (
    MAX_CLIENT_ID_CHARS,
    MAX_NAME_CHARS,
    MAX_SCOPES_CHARS,
    MAX_URL_CHARS,
    OAuthClient,
    TokenAuth,
)

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_URL_CHARS)
]
# A client id is visible ASCII (RFC 6749 appendix A.1).
ClientId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_CLIENT_ID_CHARS, pattern=r"^[ -~]+$"
    ),
]
# Space-separated scope tokens (RFC 6749 3.3), possibly none.
Scopes = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=MAX_SCOPES_CHARS,
        pattern=r"^([\x21\x23-\x5b\x5d-\x7e]+( [\x21\x23-\x5b\x5d-\x7e]+)*)?$",
    ),
]

URL_FIELDS = ("authorization_endpoint", "token_endpoint", "revocation_endpoint", "resource")


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    authorization_endpoint: Url
    token_endpoint: Url
    revocation_endpoint: Url | None = None
    client_id: ClientId
    # None: a public client (PKCE only).
    client_secret: SecretIn | None = None
    token_auth: TokenAuth = TokenAuth.POST
    scopes: Scopes = ""
    # RFC 8707: the resource (MCP server) the tokens are for; sent when set.
    resource: Url | None = None


class ClientUpdate(BaseModel):
    """Only the fields sent change; `client_secret` replaces the stored one, `null`
    removes it (a public client)."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: Name | None = None
    authorization_endpoint: Url | None = None
    token_endpoint: Url | None = None
    revocation_endpoint: Url | None = None
    client_id: ClientId | None = None
    client_secret: SecretIn | None = None
    token_auth: TokenAuth | None = None
    scopes: Scopes | None = None
    resource: Url | None = None
    # A new authorization, token or revocation endpoint disconnects every connector
    # through the client; a shared one keeps its tokens only with this set.
    keep_shared_connectors: bool = False

    @model_validator(mode="after")
    def _shape(self) -> Self:
        required = ("name", "authorization_endpoint", "token_endpoint", "client_id")
        for name in (*required, "token_auth", "scopes"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be removed")
        return self


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str | None
    client_id: str
    has_client_secret: bool
    client_secret_kind: SecretKind | None
    token_auth: TokenAuth
    scopes: str
    resource: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, client: OAuthClient) -> "ClientOut":
        ref = client.client_secret_ref
        return cls(
            id=client.id,
            name=client.name,
            authorization_endpoint=client.authorization_endpoint,
            token_endpoint=client.token_endpoint,
            revocation_endpoint=client.revocation_endpoint,
            client_id=client.client_id,
            has_client_secret=ref is not None,
            client_secret_kind=kind_of(ref) if ref is not None else None,
            token_auth=client.token_auth,
            scopes=client.scopes,
            resource=client.resource,
            version=client.version,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )


class AuthorizeOut(BaseModel):
    """Where the browser goes to approve the connection."""

    authorization_url: str


class DiscoverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: Url


class DiscoveryOut(BaseModel):
    """A proposal for an OAuth client, found from an MCP server's address; the
    endpoints are None unless `status` is `ok` (`modules/oauth/discovery.py`)."""

    status: DiscoveryStatus
    resource: str | None
    issuer: str | None
    authorization_endpoint: str | None
    token_endpoint: str | None
    revocation_endpoint: str | None
    scopes: str
    pkce: bool
    registration: bool
