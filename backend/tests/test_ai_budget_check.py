"""`budget_exhausted` (plan M7 decision 10): is a daily limit of the organisation, the
person or the agent reached today (UTC)? Tokens are in + out; a currency limit sums
only priced calls and applies only to a call that has a price."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import event

from app.modules.ai.budgets import budget_exhausted
from app.modules.ai.models import AiBudget, BudgetScope
from tests.factories_agents import Bench
from tests.test_ai_budgets import use


async def budget(bench: Bench, scope: BudgetScope, **limits: Any) -> AiBudget:
    row = AiBudget(org_id=bench.agent.org_id, **limits)
    if scope == BudgetScope.USER:
        row.user_id = bench.people.users["alice"].id
    elif scope == BudgetScope.AGENT:
        row.agent_id = bench.agent.id
    bench.session.add(row)
    await bench.session.flush()
    return row


async def exhausted(bench: Bench, *, priced: bool = True, now: datetime | None = None) -> Any:
    return await budget_exhausted(
        bench.session,
        bench.agent.org_id,
        bench.people.users["alice"].id,
        bench.agent.id,
        priced=priced,
        now=now,
    )


async def test_without_budgets_nothing_is_exhausted(bench: Bench) -> None:
    await use(bench, agent=True, tokens_in=10**6)
    assert await exhausted(bench) is None


async def test_a_token_limit_counts_in_and_out_of_today(bench: Bench) -> None:
    row = await budget(bench, BudgetScope.USER, tokens_per_day=151)
    await use(bench)  # 100 + 50
    await use(bench, who="bob", tokens_in=10**6)  # someone else's
    await use(bench, tokens_in=10**6, days_ago=1)  # yesterday's
    assert await exhausted(bench) is None
    row.tokens_per_day = 150
    await bench.session.flush()
    assert await exhausted(bench) == BudgetScope.USER
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    assert await exhausted(bench, now=tomorrow) is None  # a new day


async def test_the_organisation_counts_everyone_and_the_agent_its_own(bench: Bench) -> None:
    org = await budget(bench, BudgetScope.ORGANISATION, tokens_per_day=400)
    agent = await budget(bench, BudgetScope.AGENT, tokens_per_day=150)
    await use(bench, who="bob")
    await use(bench)
    assert await exhausted(bench) is None  # the agent used nothing yet; 400 not reached
    await use(bench, who="carol")
    assert await exhausted(bench) == BudgetScope.ORGANISATION
    org.tokens_per_day = 10**6
    await use(bench, who="bob", agent=True)  # the agent, for someone else
    await bench.session.flush()
    assert await exhausted(bench) == BudgetScope.AGENT
    assert agent.tokens_per_day == 150


async def test_a_currency_limit_counts_priced_calls_and_stops_only_priced_ones(
    bench: Bench,
) -> None:
    bench.connection.prices = {"m1": {"input": "1000", "output": "1000"}}  # 0.15 EUR a call
    await bench.session.flush()
    row = await budget(bench, BudgetScope.AGENT, cost_per_day=Decimal("0.30"))
    await use(bench, agent=True)
    await use(bench, agent=True, model="m2", tokens_in=10**6)  # unpriced: no cost
    assert await exhausted(bench) is None
    await use(bench, agent=True)
    assert await exhausted(bench) == BudgetScope.AGENT
    assert await exhausted(bench, priced=False) is None  # a call without a price goes on
    row.tokens_per_day = 1000  # but a token limit stops it as well
    await bench.session.flush()
    assert await exhausted(bench, priced=False) == BudgetScope.AGENT


async def test_the_tightest_limit_wins(bench: Bench) -> None:
    await budget(bench, BudgetScope.ORGANISATION, tokens_per_day=10**6)
    await budget(bench, BudgetScope.USER, tokens_per_day=10**5)
    await budget(bench, BudgetScope.AGENT, tokens_per_day=100)
    await use(bench, agent=True)
    assert await exhausted(bench) == BudgetScope.AGENT


async def test_every_applicable_budget_is_checked_with_one_scan(bench: Bench) -> None:
    """The budgets that apply, then one scan of the day's usage that sums each scope
    (`FILTER`), however many budgets apply."""
    await budget(bench, BudgetScope.ORGANISATION, tokens_per_day=10**6)
    await budget(bench, BudgetScope.USER, tokens_per_day=10**6)
    await budget(bench, BudgetScope.AGENT, tokens_per_day=150)
    await use(bench, agent=True)
    seen: list[str] = []

    def _seen(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        seen.append(statement)

    sync_conn = (await bench.session.connection()).sync_connection
    event.listen(sync_conn, "before_cursor_execute", _seen)
    try:
        assert await exhausted(bench) == BudgetScope.AGENT
    finally:
        event.remove(sync_conn, "before_cursor_execute", _seen)
    assert len(seen) == 2 and "FROM usage_record" in seen[1], seen
