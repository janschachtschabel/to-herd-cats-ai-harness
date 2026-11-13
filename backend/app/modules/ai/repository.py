"""The SQL of AI connections; every statement is scoped by the organisation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.ai.models import AiConnection


class ConnectionRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock_names(self) -> None:
        """Serialise creating and renaming connections of the organisation."""
        await advisory_xact_lock(self.session, f"ai.connection_names:{self.org_id}")

    async def get(self, connection_id: uuid.UUID, *, lock: bool = False) -> AiConnection | None:
        stmt = select(AiConnection).where(
            AiConnection.org_id == self.org_id, AiConnection.id == connection_id
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def page(self, after: uuid.UUID | None, limit: int) -> list[AiConnection]:
        stmt = (
            select(AiConnection)
            .where(AiConnection.org_id == self.org_id)
            .order_by(AiConnection.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(AiConnection.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def name_taken(self, name: str, other_than: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).where(
            AiConnection.org_id == self.org_id, func.lower(AiConnection.name) == name.lower()
        )
        if other_than is not None:
            stmt = stmt.where(AiConnection.id != other_than)
        return bool(await self.session.scalar(stmt))

    async def add(self, connection: AiConnection) -> AiConnection:
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def delete(self, connection: AiConnection) -> None:
        await self.session.delete(connection)
        await self.session.flush()


async def encrypted_connections(session: AsyncSession) -> list[AiConnection]:
    """Every connection with an `enc:` secret, in every organisation, locked: for the
    operator's key rotation (`scripts/rotate_secrets.py`), which acts for no one."""
    stmt = (
        select(AiConnection)
        .where(AiConnection.secret_ref.like("enc:%"))
        .order_by(AiConnection.id)
        .with_for_update()
    )
    return list((await session.scalars(stmt)).all())
