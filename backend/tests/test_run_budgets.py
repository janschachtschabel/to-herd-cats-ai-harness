"""Budgets in a run (plan M7 decision 10): checked before every model call against
today's usage; a reached limit ends the run with `budget` (journaled, a notice where it
answers), never cutting a call already sent, so a run passes a limit by at most one
call. A limit changed during a run counts at the next call. Usage is booked to the
run's person, its agent and the space of its place."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import event, select

from app.core.clock import SystemClock
from app.core.models_base import utcnow
from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.ai.models import BudgetScope, UsageRecord
from app.runtime.models import wrap_model
from tests.factories_agents import Bench
from tests.factories_writing import Work
from tests.test_ai_budget_check import budget
from tests.test_ai_budgets import BUDGETS, use


async def _stop(bench: Bench) -> dict[str, Any]:
    stop = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.STOP))
    assert stop is not None
    content: dict[str, Any] = stop.content
    return content


async def test_a_reached_limit_stops_the_run_before_its_call(bench: Bench) -> None:
    await budget(bench, BudgetScope.USER, tokens_per_day=100)
    await use(bench)  # 150 tokens of Alice's today
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.BUDGET
    assert bench.stub.state.log == []  # nothing went out
    assert await _stop(bench) == {"reason": "budget", "detail": "user"}
    (notice,) = [m for m in await bench.messages() if m["kind"] == "system"]
    assert notice["system"]["new"]["value"] == "budget"


async def test_a_call_passes_the_limit_once_and_the_next_waits(bench: Bench) -> None:
    await budget(bench, BudgetScope.AGENT, tokens_per_day=1)
    bench.stub.state.replies.extend(
        [{"tool_calls": [{"name": "search", "arguments": {"query": "x"}}]}, {"content": "no"}]
    )
    await bench.say("Such")
    assert await bench.run_next() == StopReason.BUDGET
    assert len(bench.stub.state.log) == 1  # the first call went out whole; the second not
    assert await _stop(bench) == {"reason": "budget", "detail": "agent"}
    booked = (await bench.session.scalars(select(UsageRecord))).all()
    assert len(booked) == 1 and booked[0].agent_id == bench.agent.id


async def test_a_currency_limit_stops_only_priced_calls(bench: Bench) -> None:
    bench.connection.prices = {"m1": {"input": "1000", "output": "1000"}}
    await bench.session.flush()
    await budget(bench, BudgetScope.ORGANISATION, cost_per_day=Decimal("0.10"))
    await use(bench, who="bob")  # 0.15 EUR today
    await bench.say("Eins")
    assert await bench.run_next() == StopReason.BUDGET
    assert await _stop(bench) == {"reason": "budget", "detail": "organisation"}
    bench.connection.prices = {}  # the agent's model has no price: the limit does not apply
    await bench.session.flush()
    await bench.say("Zwei")
    assert await bench.run_next() == StopReason.COMPLETED


async def test_a_limit_lowered_during_the_run_counts_at_the_next_call(bench: Bench) -> None:
    row = await budget(bench, BudgetScope.USER, tokens_per_day=10**6)
    calls = 0

    async def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            row.tokens_per_day = 1
            await bench.session.flush()
            return ModelResponse(parts=[ToolCallPart("search", {"query": "x"}, tool_call_id="c")])
        return ModelResponse(parts=[TextPart("too late")])

    executor = bench.executor(make_model=lambda target, timeout: wrap_model(FunctionModel(model)))
    await bench.say("Such")
    assert await bench.run_next(executor) == StopReason.BUDGET
    assert calls == 1


async def test_a_limit_raised_by_an_admin_lets_the_next_run_go(bench: Bench) -> None:
    await use(bench)
    put = await bench.people.admin.put(
        f"{BUDGETS}/organisation", json={"tokens_per_day": 150, "version": None}
    )
    await bench.say("Eins")
    assert await bench.run_next() == StopReason.BUDGET
    raised = await bench.people.admin.put(
        f"{BUDGETS}/organisation", json={"tokens_per_day": 10**6, "version": put.json()["version"]}
    )
    assert raised.status_code == 200, raised.text
    await bench.say("Zwei")
    assert await bench.run_next() == StopReason.COMPLETED


async def test_usage_is_booked_to_the_space_of_the_place(work: Work) -> None:
    bench = work.bench
    channel = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "c"})
    asked = await bench.people.alice.post(
        f"/api/conversations/{channel.json()['id']}/messages",
        json={"body_md": "@Ava hallo", "mentions": [str(bench.agent.id)]},
    )
    assert asked.status_code == 201, asked.text
    assert await bench.run_next() == StopReason.COMPLETED
    await bench.say("Und hier?")  # the DM: no space
    assert await bench.run_next() == StopReason.COMPLETED
    booked = (await bench.session.scalars(select(UsageRecord).order_by(UsageRecord.id))).all()
    assert [r.space_id for r in booked] == [work.space.id, None]
    assert {(r.user_id, r.agent_id) for r in booked} == {
        (bench.people.users["alice"].id, bench.agent.id)
    }


async def test_the_day_of_the_check_and_of_the_booking_comes_from_the_clock(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check before a model call and the booking of its usage take the time from
    `core/clock.py`, as the due loop's check when a term fires does: one UTC day for
    both, also under the browser tests' clock."""
    await budget(bench, BudgetScope.USER, tokens_per_day=100)
    await use(bench, days_ago=1)  # 150 tokens of Alice's yesterday
    yesterday = utcnow() - timedelta(days=1)
    monkeypatch.setattr(SystemClock, "now", lambda self: yesterday)
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.BUDGET  # yesterday's limit, reached then
    monkeypatch.setattr(SystemClock, "now", lambda self: yesterday - timedelta(days=1))
    await bench.say("Vorgestern")
    assert await bench.run_next() == StopReason.COMPLETED
    booked = await bench.session.scalar(select(UsageRecord).where(UsageRecord.run_id.is_not(None)))
    assert booked is not None and booked.created_at == yesterday - timedelta(days=1)


@contextmanager
def _statements(sync_conn: Any) -> Iterator[list[str]]:
    seen: list[str] = []

    def _seen(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        seen.append(statement)

    event.listen(sync_conn, "before_cursor_execute", _seen)
    try:
        yield seen
    finally:
        event.remove(sync_conn, "before_cursor_execute", _seen)


async def test_the_budget_is_summed_before_the_runs_row_is_locked(bench: Bench) -> None:
    """The day's sums (one scan, however many budgets apply) come before the step locks
    the run's row, so a long sum never holds a cancel or the worker's lease renewal."""
    await budget(bench, BudgetScope.ORGANISATION, tokens_per_day=10**6)
    await budget(bench, BudgetScope.USER, tokens_per_day=10**6)
    await budget(bench, BudgetScope.AGENT, tokens_per_day=10**6)
    await bench.say("Hallo")
    with _statements((await bench.session.connection()).sync_connection) as seen:
        assert await bench.run_next() == StopReason.COMPLETED
    sums = [i for i, s in enumerate(seen) if "FROM usage_record" in s and "sum(" in s]
    assert len(sums) == 1, "one scan of the day's usage for the three budgets"
    step = max(i for i, s in enumerate(seen[: sums[0]]) if s.startswith("SAVEPOINT"))
    lock = next(
        i
        for i, s in enumerate(seen)
        if i > step and re.search(r"FROM run\b", s) and "FOR UPDATE" in s
    )
    assert sums[0] < lock, "the step locked the run's row before summing the day"
