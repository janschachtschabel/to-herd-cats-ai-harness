"""The SQL of external MCP servers and their tools; every statement is scoped by the
organisation."""

import uuid

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
