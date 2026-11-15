"""One catalogue entry (plan M8 decision 10): a template for an external MCP server, as
a YAML file under `app/mcp/catalog/` or in `HERD_MCP_CATALOG_DIR`.

An entry names the server's address (with `{base_url}` for instances people run
themselves), the connector scopes and sign-in kinds it supports (for OAuth the
authorization server's endpoints and scopes, but never a client id or secret), and a
suggested `read`/`write` classification of the tools it knows. The suggestion is
never an approval: every tool is still approved one by one, and a suggestion only
ever tightens what the server's own annotation proposes.
"""

from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.ai.models import DataLocation
from app.modules.connectors.models import AuthKind
from app.modules.connectors.schemas import HeaderName, check_auth, check_header
from app.modules.mcp_servers.models import (
    MAX_NAME_CHARS,
    MAX_TOOL_NAME_CHARS,
    MAX_URL_CHARS,
    Classification,
    ConnectorUse,
)
from app.modules.oauth.models import TokenAuth
from app.modules.oauth.schemas import Scopes

BASE_URL = "{base_url}"
MAX_TOOLS = 500
MAX_TEXT_CHARS = 2000

EntryId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]
Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)
]
Template = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
ToolName = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TOOL_NAME_CHARS)]
DocUrl = Annotated[str, StringConstraints(pattern=r"^https://[^\s]+$", max_length=MAX_URL_CHARS)]


def render(template: str, base_url: str | None) -> str:
    return template.replace(BASE_URL, base_url) if base_url is not None else template


def check_https(url: str) -> None:
    """An https address with a host and nothing else (no credentials, query or
    fragment); the egress rules check it again when a server is created."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc:
        raise ValueError("an https address with a host is needed")
    if parts.query or parts.fragment or "?" in url or "#" in url:
        raise ValueError("no query or fragment")
    if any(c.isspace() for c in url):
        raise ValueError("no whitespace")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Localized(_Strict):
    de: Text
    en: Text


class BaseUrlSpec(_Strict):
    """The instance's address, which the admin may change (a self-managed GitLab)."""

    default: Template
    note: Localized | None = None

    @model_validator(mode="after")
    def _https(self) -> Self:
        check_https(self.default)
        return self


class OAuthSpec(_Strict):
    authorization_endpoint: Template
    token_endpoint: Template
    revocation_endpoint: Template | None = None
    scopes: Scopes = ""
    # Send the server's URL as the RFC 8707 resource (MCP clients must).
    resource: bool = True
    token_auth: TokenAuth = TokenAuth.POST


class AuthOption(_Strict):
    kind: AuthKind
    header_name: HeaderName | None = None
    oauth: OAuthSpec | None = None
    note: Localized | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        check_header(self.header_name)
        check_auth(self.kind, self.header_name)
        if (self.kind == AuthKind.OAUTH) != (self.oauth is not None):
            raise ValueError("oauth is needed for kind oauth, and only for it")
        return self


class CatalogEntry(_Strict):
    id: EntryId
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
    ]
    description: Localized
    url: Template
    base_url: BaseUrlSpec | None = None
    data_location: DataLocation = DataLocation.EXTERNAL
    connector_scopes: list[ConnectorUse] = Field(min_length=1, max_length=3)
    auth: list[AuthOption] = Field(default_factory=list, max_length=3)
    tools: dict[ToolName, Classification] = Field(default_factory=dict, max_length=MAX_TOOLS)
    docs: list[DocUrl] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if len(set(self.connector_scopes)) != len(self.connector_scopes):
            raise ValueError("connector_scopes repeat")
        kinds = [option.kind for option in self.auth]
        if len(set(kinds)) != len(kinds):
            raise ValueError("auth kinds repeat")
        needs_auth = set(self.connector_scopes) - {ConnectorUse.NONE}
        if needs_auth and not self.auth:
            raise ValueError("a connector scope needs at least one auth kind")
        if self.auth and not needs_auth:
            raise ValueError("auth kinds need the connector scope personal or shared")
        base = self.base_url.default if self.base_url else None
        for template in self.templates():
            if BASE_URL in template and base is None:
                raise ValueError("{base_url} needs base_url")
            if "{" in template.replace(BASE_URL, "") or "}" in template.replace(BASE_URL, ""):
                raise ValueError("only {base_url} may be filled in")
            check_https(render(template, base))
        return self

    def templates(self) -> list[str]:
        found = [self.url]
        for option in self.auth:
            if option.oauth is not None:
                spec = option.oauth
                found += [spec.authorization_endpoint, spec.token_endpoint]
                found += [spec.revocation_endpoint] if spec.revocation_endpoint else []
        return found

    def option(self, kind: AuthKind) -> AuthOption | None:
        return next((option for option in self.auth if option.kind == kind), None)
