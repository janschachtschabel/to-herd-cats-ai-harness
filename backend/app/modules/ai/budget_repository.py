"""The SQL of budgets: the rows, and what was used in a span per scope (the check
before a model call and the list beside each budget), from `usage_record` over its
indexes by organisation, person or agent and time."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, bindparam, func, literal, or_, select, true, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.agents.models import Agent
from app.modules.ai.models import AiBudget, BudgetScope, UsageRecord
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class Spent:
    tokens: int  # in + out
    cost: Decimal  # EUR, of the priced calls only
    unpriced_calls: int


NOTHING = Spent(0, Decimal(0), 0)

_SUBJECT_COLUMN = {BudgetScope.USER: UsageRecord.user_id, BudgetScope.AGENT: UsageRecord.agent_id}


class BudgetRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def applicable(self, user_id: uuid.UUID, agent_id: uuid.UUID) -> list[AiBudget]:
        """The organisation's, the person's and the agent's budget, those that exist."""
        org = (AiBudget.user_id.is_(None)) & (AiBudget.agent_id.is_(None))
        stmt = select(AiBudget).where(
            AiBudget.org_id == self.org_id,
            or_(org, AiBudget.user_id == user_id, AiBudget.agent_id == agent_id),
        )
        return list((await self.session.scalars(stmt)).all())

    async def page(self, after: uuid.UUID | None, limit: int) -> list[AiBudget]:
        stmt = select(AiBudget).where(AiBudget.org_id == self.org_id)
        if after is not None:
            stmt = stmt.where(AiBudget.id > after)
        return list((await self.session.scalars(stmt.order_by(AiBudget.id).limit(limit))).all())

    async def get(self, budget_id: uuid.UUID) -> AiBudget | None:
        stmt = (
            select(AiBudget)
            .where(AiBudget.org_id == self.org_id, AiBudget.id == budget_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def lock_subject(self, scope: BudgetScope, subject_id: uuid.UUID | None) -> None:
        """Serialise writes of one subject's budget, the first one included."""
        await advisory_xact_lock(self.session, f"ai.budget:{self.org_id}:{scope}:{subject_id}")

    async def of_subject(self, scope: BudgetScope, subject_id: uuid.UUID | None) -> AiBudget | None:
        stmt = (
            select(AiBudget)
            .where(AiBudget.org_id == self.org_id, *_subject(scope, subject_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def add(self, row: AiBudget) -> AiBudget:
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, row: AiBudget) -> None:
        await self.session.delete(row)
        await self.session.flush()

    async def spent(
        self,
        scope: BudgetScope,
        subject_ids: Collection[uuid.UUID],
        start: datetime,
        end: datetime,
    ) -> dict[uuid.UUID | None, Spent]:
        """Use in [start, end): the organisation's under None, else per subject id
        (only those with use)."""
        tokens = func.coalesce(func.sum(UsageRecord.tokens_in + UsageRecord.tokens_out), 0)
        cost = func.sum(UsageRecord.cost)
        unpriced = func.count() - func.count(UsageRecord.cost)
        span = (
            UsageRecord.org_id == self.org_id,
            UsageRecord.created_at >= start,
            UsageRecord.created_at < end,
        )
        if scope == BudgetScope.ORGANISATION:
            row = (await self.session.execute(select(tokens, cost, unpriced).where(*span))).one()
            return {None: _spent(*row)}
        if not subject_ids:
            return {}
        column = _SUBJECT_COLUMN[scope]
        stmt = (
            select(column, tokens, cost, unpriced)
            .where(*span, column.in_(subject_ids))
            .group_by(column)
        )
        rows = (await self.session.execute(stmt)).all()
        return {r[0]: _spent(r[1], r[2], r[3]) for r in rows}

    async def spent_on(
        self,
        scopes: Collection[BudgetScope],
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> dict[BudgetScope, Spent]:
        """The use in [start, end) of the organisation, the person and the agent, for
        the scopes asked, in one scan: each scope's sums `FILTER`ed from the rows of
        the span (all of the organisation's if it is asked, else the person's and the
        agent's)."""
        only = {
            BudgetScope.ORGANISATION: true(),
            BudgetScope.USER: UsageRecord.user_id == user_id,
            BudgetScope.AGENT: UsageRecord.agent_id == agent_id,
        }
        asked = [scope for scope in BudgetScope if scope in scopes]
        if not asked:
            return {}
        columns: list[ColumnElement[Any]] = []
        for scope in asked:
            where = only[scope]
            tokens = func.sum(UsageRecord.tokens_in + UsageRecord.tokens_out).filter(where)
            calls = func.count().filter(where) - func.count(UsageRecord.cost).filter(where)
            columns += [func.coalesce(tokens, 0), func.sum(UsageRecord.cost).filter(where), calls]
        rows = select(*columns).where(  # the day inline: a plan that knows the span
            UsageRecord.org_id == self.org_id,
            UsageRecord.created_at >= bindparam("start", start, literal_execute=True),
            UsageRecord.created_at < bindparam("end", end, literal_execute=True),
        )
        if BudgetScope.ORGANISATION not in asked:
            rows = rows.where(or_(only[BudgetScope.USER], only[BudgetScope.AGENT]))
        row = (await self.session.execute(rows)).one()
        return {scope: _spent(*row[3 * i : 3 * i + 3]) for i, scope in enumerate(asked)}

    async def agents(self, after: tuple[str, uuid.UUID] | None, limit: int) -> list[Agent]:
        """The organisation's agents (personal ones too) by name, then id."""
        stmt = select(Agent).where(Agent.org_id == self.org_id)
        if after is not None:
            stmt = stmt.where(
                tuple_(Agent.name, Agent.id) > tuple_(literal(after[0]), literal(after[1]))
            )
        stmt = stmt.order_by(Agent.name, Agent.id).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def names(
        self, user_ids: Collection[uuid.UUID], agent_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """Display names of the people and agents of the organisation among the ids."""
        names: dict[uuid.UUID, str] = {}
        if user_ids:
            users = select(User.id, User.name).where(
                User.org_id == self.org_id, User.id.in_(user_ids)
            )
            names |= {r[0]: r[1] for r in (await self.session.execute(users)).all()}
        if agent_ids:
            agents = select(Agent.id, Agent.name).where(
                Agent.org_id == self.org_id, Agent.id.in_(agent_ids)
            )
            names |= {r[0]: r[1] for r in (await self.session.execute(agents)).all()}
        return names


def _spent(tokens: int, cost: Decimal | None, unpriced: int) -> Spent:
    return Spent(int(tokens), Decimal(cost or 0), int(unpriced))


def _subject(scope: BudgetScope, subject_id: uuid.UUID | None) -> list[ColumnElement[bool]]:
    if scope == BudgetScope.USER:
        return [AiBudget.user_id == subject_id]
    if scope == BudgetScope.AGENT:
        return [AiBudget.agent_id == subject_id]
    return [AiBudget.user_id.is_(None), AiBudget.agent_id.is_(None)]
