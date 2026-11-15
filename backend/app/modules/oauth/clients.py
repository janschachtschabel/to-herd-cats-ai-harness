"""OAuth clients (plan M8 task 8), managed with `ai.manage`; anyone else gets 404
`ai.not_found`, as for the other AI administration.

- Endpoints and the resource pass the egress rules when written (https, no
  credentials, query or fragment, no private or metadata address written as such;
  422 `oauth_client.url_not_allowed`); names are checked again when dialled.
- The client secret arrives as a value (stored `enc:`) or an `env:HERD_AI_*` name;
  `null` makes a public client. It is in no answer, audit entry or log line.
- A client a connector or an MCP server names is not deleted (409
  `oauth_client.in_use`). Every write names the version it read (409
  `oauth_client.version_conflict`).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress, secrets
from app.core.access import Action, Actor
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.ai.access import require_ai
from app.modules.ai.schemas import SecretIn
from app.modules.audit.recorder import record
from app.modules.oauth.discovery import Discovery, discover
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.protocol import egress_for
from app.modules.oauth.repository import ClientRepository
from app.modules.oauth.schemas import URL_FIELDS, ClientCreate, ClientUpdate

_FIELDS = (
    "name",
    "authorization_endpoint",
    "token_endpoint",
    "revocation_endpoint",
    "client_id",
    "token_auth",
    "scopes",
    "resource",
)


def client_not_found() -> NotFound:
    return NotFound(code="oauth_client.not_found")


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _repo(self, actor: Actor) -> ClientRepository:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        return ClientRepository(self.session, actor.org_id)

    async def list(self, actor: Actor, params: PageParams) -> Page[OAuthClient]:
        repo = await self._repo(actor)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await repo.page(after, params.limit + 1)
        return id_page(rows, params.limit, lambda c: c.id)

    async def discover(self, actor: Actor, url: str) -> Discovery:
        """A proposal from an MCP server's address; nothing is stored."""
        await self._repo(actor)
        _check_url(url)
        return await discover(url)

    async def get(self, actor: Actor, client_id: uuid.UUID) -> OAuthClient:
        repo = await self._repo(actor)
        return _found(await repo.get(client_id))

    async def create(self, actor: Actor, data: ClientCreate) -> OAuthClient:
        repo = await self._repo(actor)
        for name in URL_FIELDS:
            _check_url(getattr(data, name))
        await repo.lock_names()
        if await repo.name_taken(data.name):
            raise Conflict(code="oauth_client.name_taken")
        client = await repo.add(
            OAuthClient(
                org_id=actor.org_id,
                **{name: getattr(data, name) for name in _FIELDS},
                client_secret_ref=_secret_ref(data.client_secret),
            )
        )
        details = {"secret": _kind(client.client_secret_ref), "token_auth": client.token_auth}
        await self._audit(actor, "oauth_client.created", client, details)
        return client

    async def update(self, actor: Actor, client_id: uuid.UUID, data: ClientUpdate) -> OAuthClient:
        repo = await self._repo(actor)
        if "name" in data.model_fields_set:
            await repo.lock_names()
        client = _found(await repo.get(client_id, lock=True))
        if client.version != data.version:
            raise Conflict(
                code="oauth_client.version_conflict",
                details={"current_version": client.version},
            )
        if data.name is not None and await repo.name_taken(data.name, other_than=client.id):
            raise Conflict(code="oauth_client.name_taken")
        changed: set[str] = set()
        for name in data.model_fields_set & set(_FIELDS):
            value = getattr(data, name)
            if name in URL_FIELDS:
                _check_url(value)
            if getattr(client, name) != value:
                setattr(client, name, value)
                changed.add(name)
        details: dict[str, Any] = {}
        if "client_secret" in data.model_fields_set:
            client.client_secret_ref = _secret_ref(data.client_secret)
            changed.add("client_secret")
            details["secret"] = _kind(client.client_secret_ref)
        client.version += 1
        await self.session.flush()
        await self._audit(
            actor, "oauth_client.updated", client, {"fields": sorted(changed), **details}
        )
        return client

    async def delete(self, actor: Actor, client_id: uuid.UUID, version: int) -> None:
        repo = await self._repo(actor)
        client = _found(await repo.get(client_id, lock=True))
        if client.version != version:
            raise Conflict(
                code="oauth_client.version_conflict",
                details={"current_version": client.version},
            )
        if await repo.in_use(client.id):
            raise Conflict(code="oauth_client.in_use")
        await repo.delete(client)
        await self._audit(actor, "oauth_client.deleted", client, {"name": client.name})

    async def _audit(
        self, actor: Actor, action: str, client: OAuthClient, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "oauth_client", client.id, details)


def _found(client: OAuthClient | None) -> OAuthClient:
    if client is None:
        raise client_not_found()
    return client


def _check_url(url: str | None) -> None:
    if url is None:
        return
    try:
        egress.check_base_url(url, egress_for(url)[0])
    except egress.EgressBlocked as blocked:
        details = {"reason": blocked.reason}
        raise ValidationFailed(code="oauth_client.url_not_allowed", details=details) from None


def _secret_ref(secret: SecretIn | None) -> str | None:
    if secret is None:
        return None
    if secret.env is not None:
        return secrets.env_ref(secret.env)
    assert secret.value is not None
    return secrets.encrypt(secret.value.get_secret_value())


def _kind(ref: str | None) -> str | None:
    return secrets.kind_of(ref).value if ref is not None else None
