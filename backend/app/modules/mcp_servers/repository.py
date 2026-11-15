"""The SQL of external MCP servers and their tools; every statement is scoped by the
organisation."""

import uuid
from collections.abc import Collection

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.connectors.models import Connector
from app.modules.mcp_servers.models import ConnectorUse, McpServer, McpServerTool, ToolState


class ServerRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock_names(self) -> None:
        await advisory_xact_lock(self.session, f"mcp_server.names:{self.org_id}")

    async def get(self, server_id: uuid.UUID, *, lock: bool = False) -> McpServer | None:
        stmt = select(McpServer).where(McpServer.org_id == self.org_id, McpServer.id == server_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def page(self, after: uuid.UUID | None, limit: int) -> list[McpServer]:
        stmt = (
            select(McpServer)
            .where(McpServer.org_id == self.org_id)
            .order_by(McpServer.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(McpServer.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def personal_page(
        self, owner_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[tuple[McpServer, uuid.UUID | None]]:
        """Enabled servers that act with each person's own connector, with the id of
        `owner_id`'s connector for each (None: not connected)."""
        stmt = (
            select(McpServer, Connector.id)
            .outerjoin(
                Connector,
                (Connector.mcp_server_id == McpServer.id) & (Connector.owner_id == owner_id),
            )
            .where(
                McpServer.org_id == self.org_id,
                McpServer.connector_scope == ConnectorUse.PERSONAL,
                McpServer.enabled.is_(True),
            )
            .order_by(McpServer.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(McpServer.id > after)
        return [(server, cid) for server, cid in (await self.session.execute(stmt)).all()]

    async def name_taken(self, name: str, other_than: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).where(
            McpServer.org_id == self.org_id, func.lower(McpServer.name) == name.lower()
        )
        if other_than is not None:
            stmt = stmt.where(McpServer.id != other_than)
        return bool(await self.session.scalar(stmt))

    async def uses_connector(self, connector_id: uuid.UUID) -> bool:
        stmt = select(func.count()).where(
            McpServer.org_id == self.org_id, McpServer.connector_id == connector_id
        )
        return bool(await self.session.scalar(stmt))

    async def urls_for(self, connectors: list[Connector]) -> dict[uuid.UUID, list[str]]:
        """Per connector, the addresses of the servers its secret goes to: a shared
        one's, every server naming it; a personal one's, the server it is bound to."""
        ids = [c.id for c in connectors]
        bound = {c.mcp_server_id: c.id for c in connectors if c.mcp_server_id is not None}
        found: dict[uuid.UUID, list[str]] = {c.id: [] for c in connectors}
        if not connectors:
            return found
        stmt = (
            select(McpServer.id, McpServer.connector_id, McpServer.url)
            .where(
                McpServer.org_id == self.org_id,
                McpServer.connector_id.in_(ids) | McpServer.id.in_(list(bound)),
            )
            .order_by(McpServer.url)
        )
        for server_id, connector_id, url in (await self.session.execute(stmt)).all():
            owner = connector_id if connector_id in found else bound.get(server_id)
            if owner is not None:
                found[owner].append(url)
        return found

    async def add(self, server: McpServer) -> McpServer:
        self.session.add(server)
        await self.session.flush()
        return server

    async def delete(self, server: McpServer) -> None:
        await self.session.delete(server)
        await self.session.flush()


class ToolRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock_approvals(self) -> None:
        """Until the transaction ends: approvals of the organisation one at a time, so
        two cannot pass the cap together."""
        await advisory_xact_lock(self.session, f"mcp_tool.approvals:{self.org_id}")

    async def approved_count(self, other_than: uuid.UUID) -> int:
        """The organisation's tools holding an approval (approved, or changed since),
        but `other_than`."""
        stmt = select(func.count()).where(
            McpServerTool.org_id == self.org_id,
            McpServerTool.approved_fingerprint.is_not(None),
            McpServerTool.id != other_than,
        )
        return int(await self.session.scalar(stmt) or 0)

    async def all_of(self, server_id: uuid.UUID) -> list[McpServerTool]:
        stmt = (
            select(McpServerTool)
            .where(McpServerTool.org_id == self.org_id, McpServerTool.server_id == server_id)
            .order_by(McpServerTool.id)
            .with_for_update()
        )
        return list((await self.session.scalars(stmt)).all())

    async def page(
        self, server_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[McpServerTool]:
        stmt = (
            select(McpServerTool)
            .where(McpServerTool.org_id == self.org_id, McpServerTool.server_id == server_id)
            .order_by(McpServerTool.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(McpServerTool.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def get(
        self, server_id: uuid.UUID, tool_id: uuid.UUID, *, lock: bool = False
    ) -> McpServerTool | None:
        stmt = select(McpServerTool).where(
            McpServerTool.org_id == self.org_id,
            McpServerTool.server_id == server_id,
            McpServerTool.id == tool_id,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def by_name(
        self, server_id: uuid.UUID, name: str, *, lock: bool = False
    ) -> McpServerTool | None:
        stmt = select(McpServerTool).where(
            McpServerTool.org_id == self.org_id,
            McpServerTool.server_id == server_id,
            McpServerTool.name == name,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def of_org(
        self, *, usable_only: bool, approved_or: Collection[uuid.UUID] | None = None
    ) -> list[tuple[McpServerTool, McpServer]]:
        """The organisation's tools with their servers, by server and tool name. With
        `usable_only`: only those a run may call now (approved, listed as approved,
        still listed, a schema that may be offered, on an enabled server). With
        `approved_or`: only those holding an approval, and those ids."""
        stmt = (
            select(McpServerTool, McpServer)
            .join(McpServer, McpServer.id == McpServerTool.server_id)
            .where(McpServerTool.org_id == self.org_id, McpServer.org_id == self.org_id)
            .order_by(McpServer.name, McpServerTool.name)
        )
        if approved_or is not None:
            stmt = stmt.where(
                McpServerTool.approved_fingerprint.is_not(None)
                | McpServerTool.id.in_(list(approved_or))
            )
        if usable_only:
            stmt = stmt.where(
                McpServer.enabled.is_(True),
                McpServerTool.state == ToolState.APPROVED,
                McpServerTool.fingerprint == McpServerTool.approved_fingerprint,
                McpServerTool.missing.is_(False),
                McpServerTool.schema_problem.is_(None),
            )
        return [(tool, server) for tool, server in (await self.session.execute(stmt)).all()]

    async def withdraw_approvals(self, server_id: uuid.UUID) -> None:
        """The server moved: what was approved there needs approval again, and no
        listing brings an old approval back."""
        await self.session.execute(
            update(McpServerTool)
            .where(
                McpServerTool.org_id == self.org_id,
                McpServerTool.server_id == server_id,
                McpServerTool.state.in_((ToolState.APPROVED, ToolState.CHANGED)),
            )
            .values(
                state=ToolState.CHANGED,
                approved_fingerprint=None,
                version=McpServerTool.version + 1,
            )
        )

    async def add(self, tool: McpServerTool) -> None:
        self.session.add(tool)
