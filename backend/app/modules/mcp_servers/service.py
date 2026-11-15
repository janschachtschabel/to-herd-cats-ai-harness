"""External MCP servers (plan M8 decision 7, task 6), managed with `ai.manage`; anyone
else gets 404 `ai.not_found`, as for the other AI administration.

- The URL is Streamable HTTP over https and passes the egress rules when written
  (`egress.check_base_url`: no credentials, query or fragment, no private or metadata
  address written as such) and again at every connection (the guard in the client).
- Creating a server reads its tool list (`ToolService.refresh`); the server is kept
  when that fails, with the state in the answer.
- A shared connector is named by id and must be one of the organisation's shared
  ones; while a server names it, it is not deleted (`connector.in_use`).
- A new URL withdraws every approval (the tools there are not the ones approved).
- Every write names the version it read (409 `mcp_server.version_conflict`); audit
  details name fields and ids, never what a server said.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress
from app.core.access import Action, Actor
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.mcp.client import RULES
from app.modules.ai.access import require_ai
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.connectors.repository import ConnectorRepository
from app.modules.mcp_servers.models import ConnectorUse, McpServer
from app.modules.mcp_servers.repository import ServerRepository, ToolRepository
from app.modules.mcp_servers.schemas import (
    PersonalServerOut,
    RefreshOut,
    ServerCreate,
    ServerUpdate,
    check_connector,
)
from app.modules.mcp_servers.tools import ToolService

_FIELDS = ("name", "url", "data_location", "connector_scope", "connector_id", "enabled")


def server_not_found() -> NotFound:
    return NotFound(code="mcp_server.not_found")


class ServerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> ServerRepository:
        return ServerRepository(self.session, actor.org_id)

    async def list(self, actor: Actor, params: PageParams) -> Page[McpServer]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(after, params.limit + 1)
        return id_page(rows, params.limit, lambda s: s.id)

    async def get(self, actor: Actor, server_id: uuid.UUID) -> McpServer:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        return found(await self.repo(actor).get(server_id))

    async def personal(self, actor: Actor, params: PageParams) -> Page[PersonalServerOut]:
        """For "my connections" (`ai.use`): the servers that need the caller's own
        connector, and whether it is there."""
        await require_ai(self.session, actor, Action.AI_USE)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).personal_page(actor.principal.id, after, params.limit + 1)
        page = id_page(rows, params.limit, lambda row: row[0].id)
        items = [
            PersonalServerOut(id=s.id, name=s.name, connected=c is not None) for s, c in page.items
        ]
        return Page[PersonalServerOut](items=items, next_cursor=page.next_cursor)

    async def create(self, actor: Actor, data: ServerCreate) -> tuple[McpServer, RefreshOut]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = self.repo(actor)
        await repo.lock_names()
        if await repo.name_taken(data.name):
            raise Conflict(code="mcp_server.name_taken")
        if data.connector_id is not None:
            await self._hold_connector(actor, data.connector_id)
        server = await repo.add(
            McpServer(
                org_id=actor.org_id,
                name=data.name,
                url=_url(data.url),
                data_location=data.data_location,
                connector_scope=data.connector_scope,
                connector_id=data.connector_id,
                enabled=data.enabled,
            )
        )
        details = {**snapshot(server, _FIELDS), "connector_id": _str(server.connector_id)}
        await self._audit(actor, "mcp_server.created", server, details)
        refresh = await ToolService(self.session).refresh(actor, server.id)
        return found(await repo.get(server.id)), refresh

    async def update(self, actor: Actor, server_id: uuid.UUID, data: ServerUpdate) -> McpServer:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = self.repo(actor)
        if "name" in data.model_fields_set:
            await repo.lock_names()
        server = await self._current(repo, server_id, data.version)
        if data.name is not None and await repo.name_taken(data.name, other_than=server.id):
            raise Conflict(code="mcp_server.name_taken")
        before = snapshot(server, _FIELDS)
        for name in data.model_fields_set & set(_FIELDS):
            value = getattr(data, name)
            setattr(server, name, _url(value) if name == "url" else value)
        if server.connector_scope != ConnectorUse.SHARED:
            server.connector_id = None
        try:
            check_connector(ConnectorUse(server.connector_scope), server.connector_id)
        except ValueError:
            raise ValidationFailed(code="mcp_server.connector_invalid") from None
        if server.connector_id is not None and server.connector_id != before["connector_id"]:
            await self._hold_connector(actor, server.connector_id)
        changed = changes(before, server)
        if "url" in changed:
            await ToolRepository(self.session, actor.org_id).withdraw_approvals(server.id)
        server.version += 1
        await self.session.flush()
        await self._audit(actor, "mcp_server.updated", server, {"fields": sorted(changed)})
        return server

    async def delete(self, actor: Actor, server_id: uuid.UUID, version: int) -> None:
        """Its tools and the personal connectors bound to it go with it."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = self.repo(actor)
        server = await self._current(repo, server_id, version)
        await repo.delete(server)
        await self._audit(actor, "mcp_server.deleted", server, {"name": server.name})

    async def _hold_connector(self, actor: Actor, connector_id: uuid.UUID) -> None:
        shared = ConnectorRepository(self.session, actor.org_id, None)
        if await shared.get_shared_lock(connector_id) is None:
            raise ValidationFailed(code="mcp_server.connector_invalid")

    async def _current(
        self, repo: ServerRepository, server_id: uuid.UUID, version: int
    ) -> McpServer:
        server = found(await repo.get(server_id, lock=True))
        if server.version != version:
            raise Conflict(
                code="mcp_server.version_conflict", details={"current_version": server.version}
            )
        return server

    async def _audit(
        self, actor: Actor, action: str, server: McpServer, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "mcp_server", server.id, details)


def found(server: McpServer | None) -> McpServer:
    if server is None:
        raise server_not_found()
    return server


def _url(url: str) -> str:
    """The URL as written (a trailing slash may matter to a server), if the egress
    rules allow it."""
    try:
        egress.check_base_url(url, RULES)
    except egress.EgressBlocked as blocked:
        details = {"reason": blocked.reason}
        raise ValidationFailed(code="mcp_server.url_not_allowed", details=details) from None
    return url


def _str(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None
