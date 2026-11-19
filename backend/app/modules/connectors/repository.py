"""The SQL of connectors; every statement is scoped by the organisation and by owner:
`owner_id` None means the organisation's shared connectors, a person's id that
person's personal ones. No statement reaches both.

A repository serves one purpose (plan M10 decision 18): `mcp` unless named, so every
M8 path sees `mcp` rows alone; `personal_of` gives a person's connectors of another
purpose (`connectors/purposes.py`). Two statements span purposes on purpose:
`name_taken` (the unique name index of M8 spans them) and what reads a connector by id
for every purpose (key rotation, a move of an OAuth app, renewal, the end of a flow:
each judged by the row's own purpose)."""

import uuid

from sqlalchemy import ColumnElement, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope, Purpose


class ConnectorRepository:
    def __init__(
        self,
        session: AsyncSession,
        org_id: uuid.UUID,
        owner_id: uuid.UUID | None,
        purpose: Purpose = Purpose.MCP,
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.owner_id = owner_id
        self.purpose = purpose

    def _owned(self) -> ColumnElement[bool]:
        owner = (
            Connector.owner_id.is_(None)
            if self.owner_id is None
            else Connector.owner_id == self.owner_id
        )
        return (Connector.org_id == self.org_id) & owner

    def _mine(self) -> ColumnElement[bool]:
        return self._owned() & (Connector.purpose == self.purpose)

    async def lock_names(self) -> None:
        """Serialise creating and renaming connectors of one owner."""
        await advisory_xact_lock(self.session, f"connector.names:{self.org_id}:{self.owner_id}")

    async def get(self, connector_id: uuid.UUID, *, lock: bool = False) -> Connector | None:
        stmt = select(Connector).where(self._mine(), Connector.id == connector_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def page(self, after: uuid.UUID | None, limit: int) -> list[Connector]:
        stmt = select(Connector).where(self._mine()).order_by(Connector.id).limit(limit)
        if after is not None:
            stmt = stmt.where(Connector.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def name_taken(self, name: str, other_than: uuid.UUID | None = None) -> bool:
        """Across purposes: the unique index on the owner's names spans them."""
        stmt = select(func.count()).where(self._owned(), func.lower(Connector.name) == name.lower())
        if other_than is not None:
            stmt = stmt.where(Connector.id != other_than)
        return bool(await self.session.scalar(stmt))

    async def get_shared_lock(self, connector_id: uuid.UUID) -> Connector | None:
        """The connector, locked shared until the transaction ends: a server that names
        it holds it against a concurrent deletion (which locks it exclusively)."""
        stmt = (
            select(Connector)
            .where(self._mine(), Connector.id == connector_id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def for_server(self, server_id: uuid.UUID) -> Connector | None:
        """The owner's connector bound to the external MCP server `server_id`."""
        stmt = select(Connector).where(self._mine(), Connector.mcp_server_id == server_id)
        return await self.session.scalar(stmt)

    async def create(
        self,
        *,
        connector_id: uuid.UUID,
        scope: ConnectorScope,
        name: str,
        auth_kind: AuthKind,
        header_name: str | None = None,
        secret_ref: str | None = None,
        oauth_client_id: uuid.UUID | None = None,
    ) -> Connector:
        """A new connector of this owner and this repository's purpose."""
        connector = Connector(
            id=connector_id,
            org_id=self.org_id,
            owner_id=self.owner_id,
            purpose=self.purpose,
            scope=scope,
            name=name,
            auth_kind=auth_kind,
            header_name=header_name,
            secret_ref=secret_ref,
            oauth_client_id=oauth_client_id,
        )
        return await self.add(connector)

    async def add(self, connector: Connector) -> Connector:
        given = connector.purpose or Purpose.MCP  # unset: the column's default
        assert given == self.purpose
        self.session.add(connector)
        await self.session.flush()
        return connector

    async def delete(self, connector: Connector) -> None:
        await self.session.delete(connector)
        await self.session.flush()


def personal_of(
    session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, purpose: Purpose
) -> ConnectorRepository:
    """The person's own connectors of `purpose` (the caller checked the right)."""
    return ConnectorRepository(session, org_id, user_id, purpose)


async def encrypted_connectors(session: AsyncSession) -> list[Connector]:
    """Every connector with an `enc:` secret (or OAuth refresh token), in every
    organisation, of every owner and purpose, locked: for the operator's key rotation
    (`scripts/rotate_secrets.py`)."""
    stmt = (
        select(Connector)
        .where(Connector.secret_ref.like("enc:%") | Connector.refresh_token_ref.like("enc:%"))
        .order_by(Connector.id)
        .with_for_update()
    )
    return list((await session.scalars(stmt)).all())


async def bound_connectors(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    server_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
) -> list[Connector]:
    """The organisation's connectors of every owner bound to the external server
    `server_id` (personal ones) or connecting through the OAuth client `client_id`,
    locked: what a move of that server or client disconnects (`connectors/moving.py`).
    Every purpose: a server's connectors are `mcp` ones, a client's are of its own
    purpose (the foreign key), and the move's rule holds for each."""
    stmt = select(Connector).where(Connector.org_id == org_id).order_by(Connector.id)
    if server_id is not None:
        stmt = stmt.where(Connector.mcp_server_id == server_id)
    if client_id is not None:
        stmt = stmt.where(Connector.oauth_client_id == client_id)
    stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return list((await session.scalars(stmt)).all())


async def delete_connectors(session: AsyncSession, connectors: list[Connector]) -> None:
    for connector in connectors:
        await session.delete(connector)
    await session.flush()


async def standing_of(
    session: AsyncSession, org_id: uuid.UUID, connector_id: uuid.UUID
) -> tuple[str, Purpose] | None:
    """A connector's scope and purpose, whoever owns it (None: no such connector): an
    OAuth flow's end learns from it which owner to look for, which right to check and
    where the browser goes next (`oauth/flow.py`)."""
    stmt = select(Connector.scope, Connector.purpose).where(
        Connector.org_id == org_id, Connector.id == connector_id
    )
    found = (await session.execute(stmt)).one_or_none()
    return None if found is None else (found[0], Purpose(found[1]))


async def lock_for_renewal(
    session: AsyncSession, org_id: uuid.UUID, connector_id: uuid.UUID, lock_timeout: str
) -> Connector | None:
    """The connector, locked and read afresh, waiting at most `lock_timeout` (a
    Postgres interval) for another renewal's lock (`oauth/tokens.py`, which compares
    its purpose with the one asked for)."""
    await session.execute(text(f"SET LOCAL lock_timeout = '{lock_timeout}'"))
    stmt = (
        select(Connector)
        .where(Connector.org_id == org_id, Connector.id == connector_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return await session.scalar(stmt)
