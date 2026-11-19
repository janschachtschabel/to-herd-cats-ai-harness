"""The SQL of OAuth clients and flows; every statement is scoped by the organisation
(the key rotation alone reads every organisation's rows, and `callback_purpose` finds
an app by its id alone for a callback reached without a session).

A client repository serves one purpose (plan M10 decision 18): `mcp` unless named, so
the AI administration and the MCP servers see `mcp` apps alone. `name_taken` spans
purposes (the unique name constraint of M8 does), and so do `in_use` and `purpose_of`,
which ask about one app by its id."""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.connectors.models import Connector, Purpose
from app.modules.mcp_servers.models import McpServer
from app.modules.oauth.models import OAuthClient, OAuthFlow


class ClientRepository:
    def __init__(
        self, session: AsyncSession, org_id: uuid.UUID, purpose: Purpose = Purpose.MCP
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.purpose = purpose

    def _mine(self) -> ColumnElement[bool]:
        return (OAuthClient.org_id == self.org_id) & (OAuthClient.purpose == self.purpose)

    async def lock_names(self) -> None:
        await advisory_xact_lock(self.session, f"oauth_client.names:{self.org_id}")

    async def get(self, client_id: uuid.UUID, *, lock: bool = False) -> OAuthClient | None:
        stmt = select(OAuthClient).where(self._mine(), OAuthClient.id == client_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def get_shared_lock(self, client_id: uuid.UUID) -> OAuthClient | None:
        """The client, held against a concurrent deletion until the transaction ends."""
        stmt = (
            select(OAuthClient)
            .where(self._mine(), OAuthClient.id == client_id)
            .with_for_update(read=True)
        )
        return await self.session.scalar(stmt)

    async def page(self, after: uuid.UUID | None, limit: int) -> list[OAuthClient]:
        stmt = select(OAuthClient).where(self._mine()).order_by(OAuthClient.id).limit(limit)
        if after is not None:
            stmt = stmt.where(OAuthClient.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def name_taken(self, name: str, other_than: uuid.UUID | None = None) -> bool:
        """Across purposes: the unique constraint on the names spans them."""
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

    async def purpose_of(self, client_id: uuid.UUID) -> Purpose | None:
        """An app's purpose, whatever it is (None: no such app): the callback learns
        where to send the browser when no flow tells it (`oauth/flow.py`)."""
        stmt = select(OAuthClient.purpose).where(
            OAuthClient.org_id == self.org_id, OAuthClient.id == client_id
        )
        found = await self.session.scalar(stmt)
        return None if found is None else Purpose(found)

    async def add(self, client: OAuthClient) -> OAuthClient:
        assert (client.purpose or Purpose.MCP) == self.purpose
        self.session.add(client)
        await self.session.flush()
        return client

    async def delete(self, client: OAuthClient) -> None:
        await self.session.delete(client)
        await self.session.flush()


async def callback_purpose(session: AsyncSession, client_id: uuid.UUID) -> Purpose | None:
    """The purpose of the app whose callback a response reached without a session
    (None: no such app). There is no organisation to scope by: the app's id is the
    callback's own path, and the answer only picks the page the browser goes to
    (`oauth/flow.py`, review of M10 task 13a R13a-5), which tells no more than the
    app's authorization requests already show (`docs/MCP.md`)."""
    found = await session.scalar(select(OAuthClient.purpose).where(OAuthClient.id == client_id))
    return None if found is None else Purpose(found)


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
