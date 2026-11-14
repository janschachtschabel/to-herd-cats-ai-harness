"""The SQL of connectors; every statement is scoped by the organisation and by owner:
`owner_id` None means the organisation's shared connectors, a person's id that
person's personal ones. No statement reaches both."""

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.connectors.models import Connector


class ConnectorRepository:
    def __init__(
        self, session: AsyncSession, org_id: uuid.UUID, owner_id: uuid.UUID | None
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.owner_id = owner_id

    def _mine(self) -> ColumnElement[bool]:
        owner = (
            Connector.owner_id.is_(None)
            if self.owner_id is None
            else Connector.owner_id == self.owner_id
        )
        return (Connector.org_id == self.org_id) & owner

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
        stmt = select(func.count()).where(self._mine(), func.lower(Connector.name) == name.lower())
        if other_than is not None:
            stmt = stmt.where(Connector.id != other_than)
        return bool(await self.session.scalar(stmt))

    async def add(self, connector: Connector) -> Connector:
        self.session.add(connector)
        await self.session.flush()
        return connector

    async def delete(self, connector: Connector) -> None:
        await self.session.delete(connector)
        await self.session.flush()


async def encrypted_connectors(session: AsyncSession) -> list[Connector]:
    """Every connector with an `enc:` secret, in every organisation and of every owner,
    locked: for the operator's key rotation (`scripts/rotate_secrets.py`)."""
    stmt = (
        select(Connector)
        .where(Connector.secret_ref.like("enc:%"))
        .order_by(Connector.id)
        .with_for_update()
    )
    return list((await session.scalars(stmt)).all())
