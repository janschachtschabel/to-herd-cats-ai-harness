"""The catalogue as the API shows it, and creating a server from an entry."""

import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.ai.models import DataLocation
from app.modules.ai.schemas import SecretIn
from app.modules.connectors.models import AuthKind
from app.modules.mcp_catalog.entry import CatalogEntry
from app.modules.mcp_catalog.loader import Problem, Source
from app.modules.mcp_servers.models import ConnectorUse
from app.modules.mcp_servers.schemas import CreatedServerOut, Name, Url
from app.modules.oauth.schemas import ClientId

# An entry is shown as it was loaded: nothing in it is secret (no client id or secret).
EntryOut = CatalogEntry


class ProblemOut(BaseModel):
    source: Source
    file: str
    reason: str

    @classmethod
    def of(cls, problem: Problem) -> "ProblemOut":
        return cls(source=problem.source, file=problem.file, reason=problem.reason)


class InstallIn(BaseModel):
    """A server (and what it needs) from a catalogue entry. The admin brings only the
    access and its scope; every tool is still approved one by one.

    - `none`: no credential.
    - `shared`: one shared connector, created here: `bearer`/`header` with `secret`,
      `oauth` with an OAuth client (`client_id`, `client_secret` if confidential),
      connected afterwards (`POST /api/ai/connectors/{id}/authorize`).
    - `personal`: each person connects their own; `oauth` creates the OAuth client
      they connect with, `bearer`/`header` need nothing more here.
    """

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None  # default: the entry's name
    base_url: Url | None = None  # entries with `base_url` only; default: the entry's
    connector_scope: ConnectorUse
    auth_kind: AuthKind | None = None
    secret: SecretIn | None = None
    client_id: ClientId | None = None
    client_secret: SecretIn | None = None
    data_location: DataLocation | None = None  # default: the entry's
    enabled: bool = True

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if (self.connector_scope == ConnectorUse.NONE) != (self.auth_kind is None):
            raise ValueError("auth_kind is needed for a connector scope, and only for one")
        oauth = self.auth_kind == AuthKind.OAUTH
        if not oauth and (self.client_id is not None or self.client_secret is not None):
            raise ValueError("client_id and client_secret go only with auth_kind oauth")
        if oauth and self.client_id is None:
            raise ValueError("auth_kind oauth needs client_id")
        fixed_shared = self.connector_scope == ConnectorUse.SHARED and self.auth_kind in (
            AuthKind.BEARER,
            AuthKind.HEADER,
        )
        if fixed_shared != (self.secret is not None):
            raise ValueError("secret is needed for a shared bearer or header connector only")
        return self


class InstallOut(BaseModel):
    server: CreatedServerOut
    # The OAuth client created for `oauth`, and the shared connector for `shared`.
    oauth_client_id: uuid.UUID | None
    connector_id: uuid.UUID | None
