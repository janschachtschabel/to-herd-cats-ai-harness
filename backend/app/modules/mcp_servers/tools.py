"""The tools of an external MCP server (plan M8 decision 7): read from the server,
approved, blocked and classified one by one (`ai.manage`).

- Reading the list (on create, on "refresh") and "test connection" talk to the server
  with no transaction open; the credential is the shared connector, or for a personal
  server the admin's own connector for it if there is one.
- A refresh adds what is new as `pending` (classification proposed `write`, or `read`
  where the server annotates it read-only and its catalogue entry suggests `read`:
  neither alone loosens, and a suggestion never approves), updates what is there (an approved
  tool whose fingerprint is no longer the approved one becomes `changed`) and marks
  what vanished `missing`.
- An approval stores the fingerprint it approved; only that exact tool is callable.
  A tool whose input schema cannot be offered to a model (`schema_view`: over 64 KiB,
  a structure too large or too deep, a property name a model cannot take) is not
  approvable (409 `mcp_tool.schema_problem`); the admin sees why (`schema_problem`).
- Classifying a tool `read` that the server does not annotate read-only needs
  `confirm_loosen` (422 `mcp_tool.loosen_unconfirmed`).
"""

import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.mcp import client as mcp
from app.mcp.client import RemoteFailure, RemoteStatus
from app.modules.ai.access import require_ai
from app.modules.audit.recorder import record
from app.modules.mcp_catalog.loader import catalog
from app.modules.mcp_servers.endpoints import prepared_endpoint
from app.modules.mcp_servers.errors import CredentialUnavailable, NotConnected
from app.modules.mcp_servers.listing import apply, new_tool, problem_of, usable
from app.modules.mcp_servers.models import Classification, McpServer, McpServerTool, ToolState
from app.modules.mcp_servers.repository import ServerRepository, ToolRepository
from app.modules.mcp_servers.schemas import RefreshOut, TestOut, ToolClassify

logger = logging.getLogger(__name__)

LIST_TIMEOUT_SECONDS = 20.0
MAX_LIST_BYTES = 2 * 1024 * 1024
MAX_TOOLS = 500


def tool_not_found() -> NotFound:
    return NotFound(code="mcp_tool.not_found")


class ToolService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _server(self, actor: Actor, server_id: uuid.UUID, *, lock: bool = False) -> McpServer:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        server = await ServerRepository(self.session, actor.org_id).get(server_id, lock=lock)
        if server is None:
            raise NotFound(code="mcp_server.not_found")
        return server

    async def refresh(self, actor: Actor, server_id: uuid.UUID) -> RefreshOut:
        server = await self._server(actor, server_id)
        url = server.url
        try:
            listed = await self._read(actor, server)
        except RemoteFailure as failure:
            result = RefreshOut(status=failure.status)
        else:
            server = await self._server(actor, server_id, lock=True)
            if server.url != url:  # moved while we read: what we read is not its list
                raise Conflict(code="mcp_server.version_conflict")
            result = await self._store(server, listed)
        await record(
            self.session,
            actor,
            "mcp_server.refreshed",
            "mcp_server",
            server_id,
            result.model_dump(),
        )
        return result

    async def test(self, actor: Actor, server_id: uuid.UUID) -> TestOut:
        """Connect, list the tools, change nothing."""
        server = await self._server(actor, server_id)
        started = time.monotonic()
        try:
            listed = await self._read(actor, server)
        except RemoteFailure as failure:
            status, count = failure.status, None
        else:
            status, count = RemoteStatus.OK, len(listed)
        return TestOut(status=status, tools=count, duration_ms=_ms_since(started))

    async def _read(self, actor: Actor, server: McpServer) -> list[mcp.ListedTool]:
        # Nothing held from here on: not while an OAuth token is renewed (a transaction
        # of its own that locks the connector), not while the server answers.
        await self.session.commit()
        try:
            endpoint, renewal = await prepared_endpoint(
                self.session, server, actor.principal.id, strict=False
            )
        except CredentialUnavailable:
            raise RemoteFailure(RemoteStatus.SECRET_UNAVAILABLE) from None
        server_id = server.id
        await self.session.commit()
        started = time.monotonic()
        status = RemoteStatus.OK
        try:
            try:
                return await self._list(endpoint)
            except RemoteFailure as failure:
                if failure.status != RemoteStatus.UNAUTHORIZED or renewal is None:
                    raise
                try:
                    endpoint = await renewal()
                except (CredentialUnavailable, NotConnected):
                    raise RemoteFailure(RemoteStatus.SECRET_UNAVAILABLE) from None
                return await self._list(endpoint)
        except RemoteFailure as failure:
            status = failure.status
            raise
        finally:
            logger.info(
                "mcp.list_tools",
                extra={
                    "mcp_server_id": str(server_id),
                    "status": status.value,
                    "duration_ms": _ms_since(started),
                },
            )

    async def _list(self, endpoint: mcp.Endpoint) -> list[mcp.ListedTool]:
        return await mcp.list_tools(
            endpoint, seconds=LIST_TIMEOUT_SECONDS, max_bytes=MAX_LIST_BYTES
        )

    async def _store(self, server: McpServer, listed: list[mcp.ListedTool]) -> RefreshOut:
        repo = ToolRepository(self.session, server.org_id)
        suggested = catalog().suggestions(server.catalog_id)
        stored = {tool.name: tool for tool in await repo.all_of(server.id)}
        new = changed = missing = 0
        seen: set[str] = set()
        # by name (stable: of two with one name the first listed), so a list over the
        # cap keeps the same tools however the server orders it
        for item in sorted(listed, key=lambda t: t.name):
            if not usable(item) or item.name in seen or len(seen) >= MAX_TOOLS:
                continue
            seen.add(item.name)
            tool = stored.pop(item.name, None)
            if tool is None:
                await repo.add(new_tool(server.org_id, server.id, item, suggested.get(item.name)))
                new += 1
            elif apply(tool, item):
                changed += 1
        for tool in stored.values():
            if not tool.missing:
                apply(tool, None)
                missing += 1
        await self.session.flush()
        return RefreshOut(status=RemoteStatus.OK, new=new, changed=changed, missing=missing)

    async def list(
        self, actor: Actor, server_id: uuid.UUID, params: PageParams
    ) -> Page[McpServerTool]:
        await self._server(actor, server_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        repo = ToolRepository(self.session, actor.org_id)
        rows = await repo.page(server_id, after, params.limit + 1)
        return id_page(rows, params.limit, lambda t: t.id)

    async def suggestions(self, actor: Actor, server_id: uuid.UUID) -> dict[str, Classification]:
        """The classifications the server's catalogue entry suggests, by tool name."""
        return catalog().suggestions((await self._server(actor, server_id)).catalog_id)

    async def approve(
        self, actor: Actor, server_id: uuid.UUID, tool_id: uuid.UUID, version: int
    ) -> McpServerTool:
        tool = await self._current(actor, server_id, tool_id, version)
        if tool.missing:
            raise Conflict(code="mcp_tool.missing")
        if problem_of(tool) is not None:  # could never be offered to a model
            raise Conflict(code="mcp_tool.schema_problem")
        tool.state = ToolState.APPROVED
        tool.approved_fingerprint = tool.fingerprint
        return await self._saved(actor, tool, "mcp_tool.approved", {"state": tool.state})

    async def block(
        self, actor: Actor, server_id: uuid.UUID, tool_id: uuid.UUID, version: int
    ) -> McpServerTool:
        tool = await self._current(actor, server_id, tool_id, version)
        tool.state = ToolState.BLOCKED
        tool.approved_fingerprint = None
        return await self._saved(actor, tool, "mcp_tool.blocked", {"state": tool.state})

    async def classify(
        self, actor: Actor, server_id: uuid.UUID, tool_id: uuid.UUID, data: ToolClassify
    ) -> McpServerTool:
        tool = await self._current(actor, server_id, tool_id, data.version)
        loosens = data.classification == Classification.READ and not tool.read_only_hint
        if loosens and not data.confirm_loosen:
            raise ValidationFailed(code="mcp_tool.loosen_unconfirmed")
        tool.classification = data.classification
        details = {"classification": data.classification, "loosened": loosens}
        return await self._saved(actor, tool, "mcp_tool.classified", details)

    async def _current(
        self, actor: Actor, server_id: uuid.UUID, tool_id: uuid.UUID, version: int
    ) -> McpServerTool:
        await self._server(actor, server_id)
        tool = await ToolRepository(self.session, actor.org_id).get(server_id, tool_id, lock=True)
        if tool is None:
            raise tool_not_found()
        if tool.version != version:
            raise Conflict(
                code="mcp_tool.version_conflict", details={"current_version": tool.version}
            )
        return tool

    async def _saved(
        self, actor: Actor, tool: McpServerTool, action: str, details: dict[str, object]
    ) -> McpServerTool:
        tool.version += 1
        await self.session.flush()
        entry = {"server_id": str(tool.server_id), **details}
        await record(self.session, actor, action, "mcp_tool", tool.id, entry)
        return tool


def _ms_since(started: float) -> int:
    return round((time.monotonic() - started) * 1000)
