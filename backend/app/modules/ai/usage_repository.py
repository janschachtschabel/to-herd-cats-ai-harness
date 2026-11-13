"""The SQL of usage: adding records, sums per UTC day and key, a person's totals."""

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Date, Label, Select, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import AiConnection, UsageRecord
from app.modules.spaces.models import Space
from app.modules.users.models import User

NO_KEY = uuid.UUID(int=0)  # rows without the grouped id (a batch without a person)


class GroupBy(StrEnum):
    USER = "user"
    AGENT = "agent"
    SPACE = "space"
    CONNECTION = "connection"


_KEY_COLUMN = {
    GroupBy.USER: UsageRecord.user_id,
    GroupBy.AGENT: UsageRecord.agent_id,
    GroupBy.SPACE: UsageRecord.space_id,
    GroupBy.CONNECTION: UsageRecord.connection_id,
}


@dataclass(frozen=True, slots=True)
class Totals:
    calls: int
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    cost: Decimal | None  # of the priced calls; None if no call had a price
    unpriced_calls: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class UsageRow:
    day: date
    key: uuid.UUID | None
    name: str | None
    totals: Totals


def _sums() -> tuple[Label[Any], ...]:
    return (
        func.count().label("calls"),
        func.coalesce(func.sum(UsageRecord.tokens_in), 0).label("tokens_in"),
        func.coalesce(func.sum(UsageRecord.tokens_out), 0).label("tokens_out"),
        func.coalesce(func.sum(UsageRecord.tokens_cached), 0).label("tokens_cached"),
        func.sum(UsageRecord.cost).label("cost"),
        (func.count() - func.count(UsageRecord.cost)).label("unpriced_calls"),
        func.coalesce(func.sum(UsageRecord.duration_ms), 0).label("duration_ms"),
    )


def _totals(row: object) -> Totals:
    return Totals(
        calls=int(row.calls),  # type: ignore[attr-defined]
        tokens_in=int(row.tokens_in),  # type: ignore[attr-defined]
        tokens_out=int(row.tokens_out),  # type: ignore[attr-defined]
        tokens_cached=int(row.tokens_cached),  # type: ignore[attr-defined]
        cost=row.cost,  # type: ignore[attr-defined]
        unpriced_calls=int(row.unpriced_calls),  # type: ignore[attr-defined]
        duration_ms=int(row.duration_ms),  # type: ignore[attr-defined]
    )


class UsageRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def add(self, record: UsageRecord) -> UsageRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def grouped(
        self,
        start: datetime,
        end: datetime,
        by: GroupBy | None,
        run_id: uuid.UUID | None,
        after: tuple[date, uuid.UUID] | None,
        limit: int,
    ) -> list[UsageRow]:
        day = cast(func.timezone("UTC", UsageRecord.created_at), Date).label("day")
        key_column = _KEY_COLUMN[by] if by is not None else literal(NO_KEY)
        key = func.coalesce(key_column, NO_KEY).label("key")
        sums = (
            select(day, key, *_sums())
            .where(
                UsageRecord.org_id == self.org_id,
                UsageRecord.created_at >= start,
                UsageRecord.created_at < end,
            )
            .group_by(day, key)
        )
        if run_id is not None:
            sums = sums.where(UsageRecord.run_id == run_id)
        grouped = sums.subquery()
        stmt = select(grouped).order_by(grouped.c.day.desc(), grouped.c.key).limit(limit)
        if after is not None:
            after_day, after_key = after
            stmt = stmt.where(
                or_(
                    grouped.c.day < after_day,
                    and_(grouped.c.day == after_day, grouped.c.key > after_key),
                )
            )
        rows = (await self.session.execute(stmt)).all()
        return [UsageRow(r.day, None if r.key == NO_KEY else r.key, None, _totals(r)) for r in rows]

    async def named(self, by: GroupBy, rows: list[UsageRow]) -> list[UsageRow]:
        """The rows with the display names of their keys, where known (agents: M5
        task 5; a deleted connection has none)."""
        ids = {r.key for r in rows if r.key is not None}
        names: dict[uuid.UUID, str] = {}
        stmt: Select[uuid.UUID, str] | None = None
        if by == GroupBy.USER:
            stmt = select(User.id, User.name).where(User.org_id == self.org_id, User.id.in_(ids))
        elif by == GroupBy.SPACE:
            stmt = select(Space.id, Space.name).where(
                Space.org_id == self.org_id, Space.id.in_(ids)
            )
        elif by == GroupBy.CONNECTION:
            stmt = select(AiConnection.id, AiConnection.name).where(
                AiConnection.org_id == self.org_id, AiConnection.id.in_(ids)
            )
        if ids and stmt is not None:
            names = {row[0]: row[1] for row in (await self.session.execute(stmt)).all()}
        return [replace(r, name=names.get(r.key) if r.key else None) for r in rows]

    async def totals_of(self, user_id: uuid.UUID, start: datetime, end: datetime) -> Totals:
        stmt = select(*_sums()).where(
            UsageRecord.org_id == self.org_id,
            UsageRecord.user_id == user_id,
            UsageRecord.created_at >= start,
            UsageRecord.created_at < end,
        )
        return _totals((await self.session.execute(stmt)).one())
