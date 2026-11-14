"""Minimal generic repository. Module repositories extend it with real queries."""

import uuid
from typing import Any

from sqlalchemy import CTE, Select, func, select
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


def locked_batch(rows: Select[Any], name: str) -> CTE:
    """`rows` (a batch: LIMIT and FOR UPDATE SKIP LOCKED) as a materialized CTE, run
    once. Written as `IN (subquery)` instead, the planner may pick a nested-loop
    semi-join that runs the subquery again per outer row, each time locking further
    rows, so the statement would touch more than LIMIT rows."""
    return rows.cte(name).prefix_with("MATERIALIZED")
