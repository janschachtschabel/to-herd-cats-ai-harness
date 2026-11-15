"""Daily budgets (spec 7.4, plan M7 decision 10): a limit in tokens (in + out) and/or
EUR per UTC day for the organisation, a person or an agent.

`budget_exhausted` is the check: before every model call of a run (`agents/
step_host.py`, which then ends the run with `budget`) and for anything else about to
start work for a person and an agent (due automations: `skipped_budget`). Every
applicable limit counts, so the tightest wins. A currency limit sums only the calls
that had a price, and it applies only to a call that has one: for a call without a
price only the token limit counts. Nothing cuts a call already sent, so concurrent
runs may each pass a limit by one call.

Admins (`ai.manage`; everyone else 404 `ai.not_found`) list, set and remove budgets;
each write names the version it read (409 `ai.budget_version_conflict`), and the list
shows today's use beside each budget.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.clock import SYSTEM_CLOCK
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import (
    Page,
    PageParams,
    decode_id_cursor,
    decode_key_cursor,
    encode_id_cursor,
    encode_key_cursor,
)
from app.modules.agents.models import Agent
from app.modules.ai.access import require_ai
from app.modules.ai.budget_repository import NOTHING, BudgetRepository, Spent
from app.modules.ai.models import AiBudget, AiConnection, BudgetScope
from app.modules.audit.recorder import record

# Which exhausted budget a stop names when several are: the most specific first.
_ORDER = (BudgetScope.USER, BudgetScope.AGENT, BudgetScope.ORGANISATION)


def utc_day(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The start and end of the UTC day of `now` (default: the clock's time, `core/
    clock.py`, as for the due loop's terms and the booking of usage)."""
    day = (now or SYSTEM_CLOCK.now()).astimezone(UTC).date()
    start = datetime.combine(day, time(), UTC)
    return start, start + timedelta(days=1)


def has_price(connection: AiConnection | None, model: str) -> bool:
    """Whether a call of `model` over the connection has a price (`usage.record_usage`)."""
    return connection is not None and model in connection.prices


def tokens_reached(budget: AiBudget, spent: Spent) -> bool:
    return budget.tokens_per_day is not None and spent.tokens >= budget.tokens_per_day


def cost_reached(budget: AiBudget, spent: Spent) -> bool:
    """For a call with a price (one without counts only toward tokens)."""
    return budget.cost_per_day is not None and spent.cost >= budget.cost_per_day


def reached(budget: AiBudget, spent: Spent, *, priced: bool = True) -> bool:
    return tokens_reached(budget, spent) or (priced and cost_reached(budget, spent))


async def budget_exhausted(
    session: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    *,
    priced: bool,
    now: datetime | None = None,
) -> BudgetScope | None:
    """The scope of a daily limit of the organisation, the person or the agent that is
    reached today (UTC), or None. `priced`: whether the call to come has a price (see
    `has_price`); without, currency limits do not apply. `now` defaults to the clock's
    time. Two statements: the budgets, then one scan of the day's usage."""
    repo = BudgetRepository(session, org_id)
    budgets = sorted(await repo.applicable(user_id, agent_id), key=lambda b: _ORDER.index(b.scope))
    if not budgets:
        return None
    start, end = utc_day(now)
    spent = await repo.spent_on({b.scope for b in budgets}, user_id, agent_id, start, end)
    for budget in budgets:
        if reached(budget, spent[budget.scope], priced=priced):
            return budget.scope
    return None


@dataclass(frozen=True, slots=True)
class BudgetView:
    budget: AiBudget
    name: str | None  # the person's or the agent's; None for the organisation
    today: Spent


class BudgetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listed(self, actor: Actor, params: PageParams) -> Page[BudgetView]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = BudgetRepository(self.session, actor.org_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await repo.page(after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_id_cursor(items[-1].id) if more else None
        return Page[BudgetView](items=await self._views(repo, items), next_cursor=cursor)

    async def agents(self, actor: Actor, params: PageParams) -> Page[Agent]:
        """Every agent of the organisation by name, to choose a budget's subject (for
        `ai.manage` alone: the agent administration needs `agent.manage`)."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        after = decode_key_cursor(params.cursor) if params.cursor else None
        rows = await BudgetRepository(self.session, actor.org_id).agents(after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_key_cursor(items[-1].name, items[-1].id) if more else None
        return Page[Agent](items=items, next_cursor=cursor)

    async def set(
        self,
        actor: Actor,
        scope: BudgetScope,
        subject_id: uuid.UUID | None,
        tokens_per_day: int | None,
        cost_per_day: Decimal | None,
        version: int | None,
    ) -> BudgetView:
        """Create (`version` None) or change the subject's budget."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        if tokens_per_day is None and cost_per_day is None:
            raise ValidationFailed(code="ai.budget_limit_missing")
        repo = BudgetRepository(self.session, actor.org_id)
        if subject_id is not None:
            await self._subject_exists(repo, scope, subject_id)
        await repo.lock_subject(scope, subject_id)
        row = await repo.of_subject(scope, subject_id)
        current = row.version if row else None
        if current != version:
            raise Conflict(code="ai.budget_version_conflict", details={"current_version": current})
        if row is None:
            row = AiBudget(org_id=actor.org_id, version=1)
            row.user_id = subject_id if scope == BudgetScope.USER else None
            row.agent_id = subject_id if scope == BudgetScope.AGENT else None
            self.session.add(row)
        else:
            row.version += 1
        row.tokens_per_day, row.cost_per_day = tokens_per_day, cost_per_day
        await self.session.flush()
        details = {
            "scope": scope.value,
            "subject_id": str(subject_id) if subject_id else None,
            "tokens_per_day": tokens_per_day,
            "cost_per_day": str(cost_per_day) if cost_per_day is not None else None,
        }
        await record(self.session, actor, "ai_budget.set", "ai_budget", row.id, details)
        (view,) = await self._views(repo, [row])
        return view

    async def delete(self, actor: Actor, budget_id: uuid.UUID, version: int) -> None:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = BudgetRepository(self.session, actor.org_id)
        row = await repo.get(budget_id)
        if row is None:
            raise NotFound(code="ai.budget_not_found")
        if row.version != version:
            raise Conflict(
                code="ai.budget_version_conflict", details={"current_version": row.version}
            )
        scope, subject = row.scope, row.subject_id
        await repo.delete(row)
        details = {"scope": scope.value, "subject_id": str(subject) if subject else None}
        await record(self.session, actor, "ai_budget.removed", "ai_budget", budget_id, details)

    async def _subject_exists(
        self, repo: BudgetRepository, scope: BudgetScope, subject_id: uuid.UUID
    ) -> None:
        user = scope == BudgetScope.USER
        names = await repo.names([subject_id] if user else [], [] if user else [subject_id])
        if subject_id not in names:
            raise NotFound(code="users.not_found" if user else "agent.not_found")

    async def _views(self, repo: BudgetRepository, rows: list[AiBudget]) -> list[BudgetView]:
        """The rows with their subject's name and today's use."""
        start, end = utc_day()
        users = [r.user_id for r in rows if r.user_id is not None]
        agents = [r.agent_id for r in rows if r.agent_id is not None]
        names = await repo.names(users, agents)
        spent: dict[BudgetScope, dict[uuid.UUID | None, Spent]] = {
            BudgetScope.USER: await repo.spent(BudgetScope.USER, users, start, end),
            BudgetScope.AGENT: await repo.spent(BudgetScope.AGENT, agents, start, end),
        }
        if any(r.scope == BudgetScope.ORGANISATION for r in rows):
            org = BudgetScope.ORGANISATION
            spent[org] = await repo.spent(org, [], start, end)
        views = []
        for row in rows:
            subject = row.subject_id
            today = spent[row.scope].get(subject, NOTHING)
            views.append(BudgetView(row, names.get(subject) if subject else None, today))
        return views
