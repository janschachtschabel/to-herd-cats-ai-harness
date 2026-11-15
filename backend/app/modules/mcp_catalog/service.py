"""The catalogue (plan M8 decision 10, task 9), for `ai.manage` (anyone else: 404
`ai.not_found`): its entries, the files that could not be loaded, and creating a server
from an entry.

Creating goes through the same services as by hand, in one transaction (OAuth client,
shared connector, server; each audited as usual, the server also with its
`catalog_id`), so every rule holds: names unique, URLs through the egress rules,
secrets only as references. The admin brings the access and its scope; the entry
only suggests classifications, and every tool still waits for approval.
"""

import base64
import binascii
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress
from app.core.access import Action, Actor
from app.core.errors import NotFound, ValidationFailed
from app.core.pagination import Page, PageParams
from app.modules.ai.access import require_ai
from app.modules.connectors.models import AuthKind, ConnectorScope
from app.modules.connectors.schemas import ConnectorCreate
from app.modules.connectors.service import ConnectorService
from app.modules.mcp_catalog.entry import AuthOption, CatalogEntry, render
from app.modules.mcp_catalog.loader import Problem, catalog
from app.modules.mcp_catalog.schemas import InstallIn, InstallOut
from app.modules.mcp_servers.endpoints import server_rules
from app.modules.mcp_servers.models import ConnectorUse
from app.modules.mcp_servers.schemas import CreatedServerOut, ServerCreate, ServerOut
from app.modules.mcp_servers.service import ServerService
from app.modules.oauth.clients import ClientService
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.schemas import ClientCreate


def entry_not_found() -> NotFound:
    return NotFound(code="mcp_catalog.not_found")


def _invalid(field: str) -> ValidationFailed:
    return ValidationFailed(code="mcp_catalog.install_invalid", details={"field": field})


def _cursor(position: str) -> str:
    return base64.urlsafe_b64encode(position.encode()).decode().rstrip("=")


def _position(cursor: str | None) -> str:
    if cursor is None:
        return ""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        position = base64.b64decode(padded, altchars=b"-_", validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        position = "\x00"
    if not position.isprintable() or not position:
        raise ValidationFailed("Invalid cursor", code="validation_failed")
    return position


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, actor: Actor, params: PageParams) -> Page[CatalogEntry]:
        """By id; the cursor is the last id shown."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        after = _position(params.cursor)
        rest = [entry for key, entry in catalog().entries.items() if key > after]
        items = rest[: params.limit]
        more = len(rest) > params.limit
        return Page[CatalogEntry](items=items, next_cursor=_cursor(items[-1].id) if more else None)

    async def problems(self, actor: Actor, params: PageParams) -> Page[Problem]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        start = _position(params.cursor)
        if start and not start.isdigit():
            raise ValidationFailed("Invalid cursor", code="validation_failed")
        offset = int(start or 0)
        found = catalog().problems
        items = list(found[offset : offset + params.limit])
        end = offset + len(items)
        return Page[Problem](
            items=items, next_cursor=_cursor(str(end)) if end < len(found) else None
        )

    async def get(self, actor: Actor, entry_id: str) -> CatalogEntry:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        entry = catalog().entries.get(entry_id)
        if entry is None:
            raise entry_not_found()
        return entry

    async def install(self, actor: Actor, entry_id: str, data: InstallIn) -> InstallOut:
        entry = await self.get(actor, entry_id)
        if data.connector_scope not in entry.connector_scopes:
            raise _invalid("connector_scope")
        option = entry.option(data.auth_kind) if data.auth_kind is not None else None
        if data.auth_kind is not None and option is None:
            raise _invalid("auth_kind")
        base_url = _base_url(entry, data.base_url)
        url = render(entry.url, base_url)
        name = data.name or entry.name
        client = await self._client(actor, name, url, base_url, option, data)
        connector_id = None
        if data.connector_scope == ConnectorUse.SHARED:
            assert option is not None
            connector_id = await self._shared_connector(actor, name, option, client, data)
        personal_client = client if data.connector_scope == ConnectorUse.PERSONAL else None
        try:
            server_data = ServerCreate(
                name=name,
                url=url,
                data_location=data.data_location or entry.data_location,
                connector_scope=data.connector_scope,
                connector_id=connector_id,
                oauth_client_id=personal_client.id if personal_client else None,
                enabled=data.enabled,
            )
        except ValidationError:
            raise _invalid("url") from None
        server, refresh = await ServerService(self.session).create(
            actor, server_data, catalog_id=entry.id
        )
        return InstallOut(
            server=CreatedServerOut(**ServerOut.of(server).model_dump(), refresh=refresh),
            oauth_client_id=client.id if client else None,
            connector_id=connector_id,
        )

    async def _client(
        self,
        actor: Actor,
        name: str,
        url: str,
        base_url: str | None,
        option: AuthOption | None,
        data: InstallIn,
    ) -> OAuthClient | None:
        if option is None or option.oauth is None:
            return None
        spec = option.oauth
        assert data.client_id is not None
        revocation = spec.revocation_endpoint
        try:
            body = ClientCreate(
                name=name,
                authorization_endpoint=render(spec.authorization_endpoint, base_url),
                token_endpoint=render(spec.token_endpoint, base_url),
                revocation_endpoint=render(revocation, base_url) if revocation else None,
                client_id=data.client_id,
                client_secret=data.client_secret,
                token_auth=spec.token_auth,
                scopes=spec.scopes,
                resource=url if spec.resource else None,
            )
        except ValidationError:
            raise _invalid("base_url") from None
        return await ClientService(self.session).create(actor, body)

    async def _shared_connector(
        self,
        actor: Actor,
        name: str,
        option: AuthOption,
        client: OAuthClient | None,
        data: InstallIn,
    ) -> uuid.UUID:
        body = ConnectorCreate(
            name=name,
            auth_kind=option.kind,
            header_name=option.header_name,
            secret=data.secret if option.kind != AuthKind.OAUTH else None,
            oauth_client_id=client.id if client else None,
        )
        connector = await ConnectorService(self.session).create(actor, ConnectorScope.SHARED, body)
        return connector.id


def _base_url(entry: CatalogEntry, given: str | None) -> str | None:
    """The instance's address as the egress rules allow it, without a trailing slash."""
    if entry.base_url is None:
        if given is not None:
            raise _invalid("base_url")
        return None
    try:
        return egress.check_base_url(given or entry.base_url.default, server_rules())
    except egress.EgressBlocked as blocked:
        raise ValidationFailed(
            code="mcp_catalog.base_url_not_allowed", details={"reason": blocked.reason}
        ) from None
