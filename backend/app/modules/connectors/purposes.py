"""What a connector or an OAuth client is for (plan M10 decision 18, task 13a).

- `mcp`: everything of M8. Shared connectors and OAuth apps are managed with
  `ai.manage`, personal connectors with `ai.use`; without the right the AI
  administration answers 404 `ai.not_found`. The M8 services (`connectors/service.py`,
  `oauth/clients.py`, `mcp_servers`) see `mcp` rows alone: a row of another purpose
  answers there like an unknown id and is in no list.
- `calendar`: a person's access to her external calendar. It belongs to her
  (personal, never shared, no MCP server) and needs `calendar.sync`, not `ai.use`: the
  calendar works without AI (goal 1 of the spec). The Google app is managed with
  `calendar.manage`. Without the right: 403 `auth.permission_denied`, as everywhere in
  the calendar.

A connector is used only for its purpose (`credentials.headers_for` refuses the
other, `WrongPurpose`), and connects through an app of its own purpose (a foreign key
in the database). The OAuth callback is each app's own (`oauth/callbacks.py`); the
connector's purpose decides which right the callback checks again and where the
browser goes afterwards (`Rule.return_to`). Extra parameters of the authorization
request come from the purpose (`Rule.extra_authorization`), never from a column.

`create_personal` is how the calendar (task 13c) stores a person's access: the secret
`enc:` only, a generated name (`calendar:<id>`, never typed by anyone: connector names
are unique per owner across purposes, so a typed one could collide with an MCP one),
the origin it was given for in the audit entry, never the secret."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlsplit

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core import secrets
from app.core.access import Action, Actor, require
from app.core.errors import Forbidden, ValidationFailed
from app.core.principal import PrincipalType
from app.modules.ai.access import require_ai
from app.modules.audit.recorder import record
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope, Purpose
from app.modules.connectors.repository import ConnectorRepository, personal_of
from app.modules.connectors.schemas import check_auth, check_header
from app.modules.oauth.repository import ClientRepository

__all__ = [
    "Purpose",
    "Rule",
    "create_personal",
    "personal_repository",
    "require_right",
    "rule_for",
]


@dataclass(frozen=True, slots=True)
class Rule:
    use: Action  # connecting one's own connector, and finishing its OAuth flow
    manage: Action  # managing the purpose's OAuth apps (and shared connectors: `mcp`)
    return_to: str  # the page the OAuth callback sends the browser to
    extra_authorization: Mapping[str, str]  # added to the authorization request


_RULES: Mapping[Purpose, Rule] = {
    Purpose.MCP: Rule(Action.AI_USE, Action.AI_MANAGE, "/ai/oauth/done", MappingProxyType({})),
    Purpose.CALENDAR: Rule(
        Action.CALENDAR_SYNC,
        Action.CALENDAR_MANAGE,
        "/calendar/accounts",
        # Google gives a refresh token only for offline access, and again only when
        # asked to show the consent once more (a reconnect after a revocation).
        MappingProxyType({"access_type": "offline", "prompt": "consent"}),
    ),
}


def rule_for(purpose: Purpose) -> Rule:
    return _RULES[purpose]


async def require_right(
    session: AsyncSession, actor: Actor, purpose: Purpose, action: Action
) -> None:
    """`mcp`: hidden without the right (404 `ai.not_found`); `calendar`: 403."""
    if purpose == Purpose.MCP:
        await require_ai(session, actor, action)
    else:
        await require(session, actor, action)


async def personal_repository(
    session: AsyncSession, actor: Actor, purpose: Purpose
) -> ConnectorRepository:
    """The acting person's own connectors of `purpose`, after checking `rule.use`."""
    if actor.principal.type != PrincipalType.USER:
        if purpose == Purpose.MCP:
            await require_ai(session, actor, Action.AI_USE)  # agents: 404, as in M8
        raise Forbidden(code="auth.permission_denied")
    await require_right(session, actor, purpose, rule_for(purpose).use)
    return personal_of(session, actor.org_id, actor.principal.id, purpose)


def bare_origin(origin: str) -> str:
    """`https://host[:port]`, lower case; 422 `connector.origin_invalid` for anything
    else (another scheme, credentials, a path, a query or a fragment)."""
    parts = urlsplit(origin)
    try:
        port = parts.port
    except ValueError:
        port = -1
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path
        or parts.query
        or parts.fragment
        or port == -1
    ):
        raise ValidationFailed(code="connector.origin_invalid")
    return f"https://{parts.hostname.lower()}" + (f":{port}" if port else "")


async def create_personal(
    session: AsyncSession,
    actor: Actor,
    *,
    purpose: Purpose,
    kind: AuthKind,
    origin: str,
    secret: SecretStr | None = None,
    header_name: str | None = None,
    oauth_client_id: uuid.UUID | None = None,
) -> Connector:
    """The acting person's new connector of `purpose` (checks `rule.use`). `bearer` and
    `header` take the secret (stored `enc:`); `oauth` names an app of the same purpose
    and gets its tokens through the flow (`oauth/flow.py`)."""
    repo = await personal_repository(session, actor, purpose)
    where = bare_origin(origin)
    try:
        check_auth(kind, header_name)
        check_header(header_name)
    except ValueError:
        raise ValidationFailed(code="connector.header_name_invalid") from None
    if (kind == AuthKind.OAUTH) != (oauth_client_id is not None) or (
        (kind == AuthKind.OAUTH) == (secret is not None)
    ):
        raise ValidationFailed(code="connector.secret_invalid")
    if oauth_client_id is not None:
        clients = ClientRepository(session, actor.org_id, purpose)
        if await clients.get_shared_lock(oauth_client_id) is None:
            raise ValidationFailed(code="connector.oauth_client_invalid")
    connector_id = uuid7()
    connector = await repo.create(
        id=connector_id,
        scope=ConnectorScope.PERSONAL,
        name=f"{purpose.value}:{connector_id}",
        auth_kind=kind,
        header_name=header_name,
        secret_ref=secrets.encrypt(secret.get_secret_value()) if secret else None,
        oauth_client_id=oauth_client_id,
    )
    details = {
        "scope": ConnectorScope.PERSONAL.value,
        "purpose": purpose.value,
        "auth_kind": kind.value,
        "origin": where,
        "secret": "enc" if secret else None,
    }
    await record(session, actor, "connector.created", "connector", connector.id, details)
    return connector
