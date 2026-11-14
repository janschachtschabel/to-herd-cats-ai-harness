"""The SQL of the run view (`run_view.py`): runs with their agent's and asker's names,
their place, whether a cancel was asked, and their usage totals; one statement for a
page of runs and one for the page's totals, whatever its length. Scoped by the
organisation; who may see which runs is the caller's filter (`user_id`, `agent_id`).

The place's space (and the page or ticket of a thread) is given only where the
reader's visible spaces (`visible`, the core's SQL) hold it; the kind and the
conversation stay."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent, Run, RunCancelRequest, RunState, StopReason
from app.modules.ai.models import UsageRecord
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.tickets.models import WorkItem
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class RunFilter:
    """Who may see which runs (`user_id` or `agent_id`, set by the service) and what
    the reader asked for."""

    user_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    state: RunState | None = None
    stop_reason: StopReason | None = None
    since: datetime | None = None
    until: datetime | None = None


@dataclass(frozen=True, slots=True)
class Place:
    kind: ConversationKind
    conversation_id: uuid.UUID
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None
    ticket_number: int | None


@dataclass(frozen=True, slots=True)
class RunTotals:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0
    cost: Decimal | None = None  # of the priced calls; None if none had a price


@dataclass(frozen=True, slots=True)
class RunRow:
    run: Run
    agent_name: str
    asker_name: str
    place: Place
    cancel_requested: bool


class RunViewRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def rows(
        self, found: RunFilter, visible: Select[uuid.UUID], after: uuid.UUID | None, limit: int
    ) -> list[RunRow]:
        """Newest first (ids are UUIDv7); `after`: the last id of the page before."""
        shown = Conversation.space_id.in_(visible)
        asked = exists().where(
            RunCancelRequest.org_id == self.org_id, RunCancelRequest.run_id == Run.id
        )
        number = (
            select(WorkItem.number)
            .where(WorkItem.org_id == self.org_id, WorkItem.id == Conversation.work_item_id)
            .scalar_subquery()
        )
        stmt = (
            select(
                Run,
                Agent.name,
                User.name,
                Conversation.kind,
                case((shown, Conversation.space_id)),
                case((shown, Conversation.page_id)),
                case((shown, number)),
                asked,
            )
            .join(Agent, Agent.id == Run.agent_id)
            .join(User, User.id == Run.user_id)
            .join(Conversation, Conversation.id == Run.conversation_id)
            .where(
                Run.org_id == self.org_id,
                Agent.org_id == self.org_id,
                User.org_id == self.org_id,
                Conversation.org_id == self.org_id,
            )
            .order_by(Run.id.desc())
            .limit(limit)
        )
        stmt = _filtered(stmt, found)
        if after is not None:
            stmt = stmt.where(Run.id < after)
        result = await self.session.execute(stmt)
        return [
            RunRow(
                run,
                agent_name,
                asker_name,
                Place(ConversationKind(kind), run.conversation_id, space_id, page_id, ticket),
                bool(cancel),
            )
            for run, agent_name, asker_name, kind, space_id, page_id, ticket, cancel in result
        ]

    async def totals(self, run_ids: list[uuid.UUID]) -> dict[uuid.UUID, RunTotals]:
        """The usage records' sums per run (runs without records are left out)."""
        if not run_ids:
            return {}
        stmt = (
            select(
                UsageRecord.run_id,
                func.count(),
                func.sum(UsageRecord.tokens_in),
                func.sum(UsageRecord.tokens_out),
                func.sum(UsageRecord.tokens_cached),
                func.sum(UsageRecord.cost),
            )
            .where(UsageRecord.org_id == self.org_id, UsageRecord.run_id.in_(run_ids))
            .group_by(UsageRecord.run_id)
        )
        return {
            run_id: RunTotals(int(calls), int(t_in), int(t_out), int(cached), cost)
            for run_id, calls, t_in, t_out, cached, cost in await self.session.execute(stmt)
            if run_id is not None
        }


def _filtered[T: tuple[object, ...]](stmt: Select[T], found: RunFilter) -> Select[T]:
    if found.user_id is not None:
        stmt = stmt.where(Run.user_id == found.user_id)
    if found.agent_id is not None:
        stmt = stmt.where(Run.agent_id == found.agent_id)
    if found.run_id is not None:
        stmt = stmt.where(Run.id == found.run_id)
    if found.state is not None:
        stmt = stmt.where(Run.state == found.state)
    if found.stop_reason is not None:
        stmt = stmt.where(Run.stop_reason == found.stop_reason)
    if found.since is not None:
        stmt = stmt.where(Run.created_at >= found.since)
    if found.until is not None:
        stmt = stmt.where(Run.created_at < found.until)
    return stmt
