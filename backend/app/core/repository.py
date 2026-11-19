"""Minimal generic repository. Module repositories extend it with real queries."""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import CTE, ColumnElement, Select, func, literal, select, tuple_
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


async def limit_time(session: AsyncSession, lock_ms: int, statement_ms: int) -> None:
    """Until the transaction ends, a lock wait ends after `lock_ms` and a statement
    after `statement_ms` (SQLSTATE 55P03, 57014: `db_errors.is_timeout`)."""
    await session.execute(
        select(
            func.set_config("lock_timeout", f"{max(1, lock_ms)}ms", True),
            func.set_config("statement_timeout", f"{max(1, statement_ms)}ms", True),
        )
    )


@dataclass(frozen=True, slots=True)
class DayKey:
    """Where a page of a list ordered by (day, id) starts: from `day` on, and on `day`
    itself only after `after_id` (None: the whole of `day`)."""

    day: date
    after_id: uuid.UUID | None = None


def from_day(
    day: ColumnElement[date], id_: ColumnElement[uuid.UUID], key: DayKey | None
) -> ColumnElement[bool]:
    """The rows at or after `key` in the order (day, id); every row without one."""
    if key is None:
        return literal(True)
    if key.after_id is None:
        return day >= key.day
    return tuple_(day, id_) > tuple_(literal(key.day), literal(key.after_id))
