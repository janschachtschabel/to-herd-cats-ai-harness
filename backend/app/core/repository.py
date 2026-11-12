"""Minimal generic repository. Module repositories extend it with real queries."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import Base


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, org_id: uuid.UUID, id_: uuid.UUID) -> ModelT | None:
        stmt = select(self.model).where(self.model.id == id_, self.model.org_id == org_id)  # type: ignore[attr-defined]
        return await self.session.scalar(stmt)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()


async def advisory_xact_lock(session: AsyncSession, key: str) -> None:
    """Serialise writers on `key` until the transaction ends (across all replicas)."""
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
