"""The SQL of OAuth clients and flows; every statement is scoped by the organisation
(the key rotation alone reads every organisation's rows)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.connectors.models import Connector
from app.modules.mcp_servers.models import McpServer
from app.modules.oauth.models import OAuthClient, OAuthFlow


class ClientRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock_names(self) -> None:
        await advisory_xact_lock(self.session, f"oauth_client.names:{self.org_id}")

    async def get(self, client_id: uuid.UUID, *, lock: bool = False) -> OAuthClient | None:
        stmt = select(OAuthClient).where(
            OAuthClient.org_id == self.org_id, OAuthClient.id == client_id
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def get_shared_lock(self, client_id: uuid.UUID) -> OAuthClient | None:
        """The client, held against a concurrent deletion until the transaction ends."""
        stmt = (
            select(OAuthClient)
            .where(OAuthClient.org_id == self.org_id, OAuthClient.id == client_id)
            .with_for_update(read=True)
        )
        return await self.session.scalar(stmt)

    async def page(self, after: uuid.UUID | None, limit: int) -> list[OAuthClient]:
        stmt = (
            select(OAuthClient)
            .where(OAuthClient.org_id == self.org_id)
            .order_by(OAuthClient.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(OAuthClient.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def name_taken(self, name: str, other_than: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).where(
            OAuthClient.org_id == self.org_id, func.lower(OAuthClient.name) == name.lower()
        )
        if other_than is not None:
            stmt = stmt.where(OAuthClient.id != other_than)
        return bool(await self.session.scalar(stmt))

    async def in_use(self, client_id: uuid.UUID) -> bool:
        connectors = select(Connector.id).where(
            Connector.org_id == self.org_id, Connector.oauth_client_id == client_id
        )
        servers = select(McpServer.id).where(
            McpServer.org_id == self.org_id, McpServer.oauth_client_id == client_id
        )
        stmt = select(or_(connectors.exists(), servers.exists()))
        return bool(await self.session.scalar(stmt))

    async def add(self, client: OAuthClient) -> OAuthClient:
        self.session.add(client)
        await self.session.flush()
        return client

    async def delete(self, client: OAuthClient) -> None:
        await self.session.delete(client)
        await self.session.flush()


class FlowRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def add(self, flow: OAuthFlow) -> None:
        self.session.add(flow)
        await self.session.flush()

    async def drop_expired(self, now: datetime) -> None:
        await self.session.execute(
            delete(OAuthFlow).where(OAuthFlow.org_id == self.org_id, OAuthFlow.expires_at <= now)
        )

    async def take(self, state_hash: str, session_id: uuid.UUID, now: datetime) -> OAuthFlow | None:
        """The flow `state_hash` names, if the login session `session_id` started it and
        it has not expired, deleted in the same statement: a second callback finds
        nothing."""
        stmt = (
            delete(OAuthFlow)
            .where(
                OAuthFlow.org_id == self.org_id,
                OAuthFlow.state_hash == state_hash,
                OAuthFlow.session_id == session_id,
                OAuthFlow.expires_at > now,
            )
            .returning(OAuthFlow)
        )
        return (await self.session.scalars(stmt)).one_or_none()


async def encrypted_clients(session: AsyncSession) -> list[OAuthClient]:
    """Every client with an `enc:` secret, in every organisation, locked: for the key
    rotation (`scripts/rotate_secrets.py`)."""
    stmt = (
        select(OAuthClient)
        .where(OAuthClient.client_secret_ref.like("enc:%"))
        .order_by(OAuthClient.id)
        .with_for_update()
    )
    return list((await session.scalars(stmt)).all())


async def all_flows(session: AsyncSession) -> list[OAuthFlow]:
    """Every open flow, locked: its verifier rotates too."""
    stmt = select(OAuthFlow).order_by(OAuthFlow.id).with_for_update()
    return list((await session.scalars(stmt)).all())
