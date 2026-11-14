"""A run's lease and the bounds of its steps (module review M6, findings 3 and 14).

- The worker's one renewal statement passes over a run whose step holds its row (a
  run inside its own step is alive) and still renews the others; the step sets the
  lease when it commits.
- A tool's step waits for a lock and runs a statement only so long; a tool that
  takes too long gets an error the model sees, and the run goes on.
- The run's deadline cuts a tool call as it cuts a model call.
- A step the database rolled back as a deadlock's victim is tried once more.
"""

import asyncio
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.models_base import utcnow
from app.modules.agents import step_checks, step_host
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import RunSteps, claim, renew
from app.modules.agents.models import EventKind, Run, RunEvent, StopReason
from app.modules.agents.step_host import RunHost, units_of
from app.runtime.models import BuiltModel, ModelTarget
from tests.factories_agents import LEASE, Bench
from tests.real_db import MakeRealClient, RealDb
from tests.support import probe_tools
from tests.support.openai_stub import OpenAIStub
from tests.support.probe_tools import CONFLICTS
from tests.test_run_worker import _setup


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


@pytest.fixture(autouse=True)
def _probes(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    probe_tools.installed(monkeypatch)
    CONFLICTS.clear()
    yield
    CONFLICTS.clear()


async def test_a_long_step_does_not_stop_the_other_runs_leases(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    await _setup(real_db, make_real_client, openai_stub)  # two DMs, a run queued in each
    unit = units_of(real_db.database.session_factory)
    async with unit() as session:
        busy = await claim(session, LEASE)
    async with unit() as session:
        free = await claim(session, LEASE)
    assert busy is not None and free is not None
    before = (await _run(real_db, free.id)).lease_until
    async with real_db.database.session_factory() as step, step.begin():
        assert await RunSteps(step, busy).owned() is not None  # as every step does first

        async def renewal() -> set[uuid.UUID]:
            async with unit() as session:
                held = {busy.id: busy.attempt, free.id: free.attempt}
                return await renew(session, held, LEASE + 60)

        task = asyncio.create_task(renewal())
        done, _ = await asyncio.wait({task}, timeout=2.0)
        if not done:
            await step.rollback()  # let it through, so the test ends
            await task
        assert done, "renew() waits for the step's row lock: every lease of the worker stalls"
        assert task.result() == {busy.id, free.id}  # the busy one is alive: in its step
    after = (await _run(real_db, free.id)).lease_until
    assert before is not None and after is not None and after > before


async def test_renewal_keeps_nothing_another_take_up_holds(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    await _setup(real_db, make_real_client, openai_stub)
    unit = units_of(real_db.database.session_factory)
    async with unit() as session:
        mine = await claim(session, LEASE)
    assert mine is not None
    async with unit() as session:
        assert await renew(session, {mine.id: mine.attempt + 1}, LEASE) == set()


async def test_a_step_sets_the_lease_when_it_commits(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench.stub.state.replies.extend([call("probe_write", label="x"), {"content": "Done."}])
    run_id = (await bench.say("Do it"))["agent_run"]["id"]
    leases: list[Any] = []
    call_tool, before_model_call = RunHost.call_tool, RunHost.before_model_call

    async def aged(self: RunHost, step: int, *args: Any) -> Any:
        run = await bench.run_of(run_id)  # the step begins with little lease left
        run.lease_until = utcnow() + timedelta(seconds=1)
        await bench.session.flush()
        return await call_tool(self, step, *args)

    async def look(self: RunHost, step: int) -> None:
        if step == 2:
            leases.append((await bench.run_of(run_id)).lease_until)
        await before_model_call(self, step)

    monkeypatch.setattr(RunHost, "call_tool", aged)
    monkeypatch.setattr(RunHost, "before_model_call", look)
    assert await bench.run_next() == StopReason.COMPLETED
    assert leases[0] > utcnow() + timedelta(seconds=LEASE - 10)


async def test_a_tool_waiting_too_long_for_a_lock_answers_an_error_the_model_sees(
    bench: Bench, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(step_host, "STEP_LOCK_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(step_checks, "STEP_LOCK_TIMEOUT_SECONDS", 0.2)
    bench.stub.state.replies.extend([call("probe_lock", label="busy"), {"content": "Later."}])
    await bench.say("Do it")
    async with engine.connect() as other:
        await other.execute(select(func.pg_advisory_lock(func.hashtext("busy"))))
        try:
            started = time.monotonic()
            assert await bench.run_next() == StopReason.COMPLETED
            assert time.monotonic() - started < 5
        finally:
            await other.execute(select(func.pg_advisory_unlock(func.hashtext("busy"))))
    assert step_host.TOOL_TIMED_OUT in bench.stub.state.log[1].text
    tools = await bench.session.scalars(
        select(RunEvent.content).where(RunEvent.kind == EventKind.TOOL_CALL)
    )
    assert [c["text"] for c in tools] == [step_host.TOOL_TIMED_OUT]  # replayed as it was


class Skewed:
    """A clock that jumps ahead once the model is made (after the run's deadline is
    set), so a run of 10 seconds has `left` seconds left."""

    def __init__(self, left: float, runtime: float) -> None:
        self.skew = 0.0
        self.jump = runtime - left

    def __call__(self) -> float:
        return time.monotonic() + self.skew


@pytest.mark.parametrize("label", ["db:30", "loop:30"])
async def test_the_deadline_cuts_a_tool_call(bench: Bench, label: str) -> None:
    bench.agent.max_runtime_seconds = 10
    await bench.session.flush()
    clock = Skewed(left=1.0, runtime=10)
    real = bench.make_model

    def make_model(target: ModelTarget, timeout: float) -> BuiltModel:
        clock.skew = clock.jump
        return real(target, timeout)

    bench.stub.state.replies.extend([call("probe_sleep", label=label), {"content": "-"}])
    await bench.say("Hi")
    started = time.monotonic()
    executor = Executor(bench.unit(), make_model=make_model, clock=clock)
    assert await bench.run_next(executor) == StopReason.DEADLINE
    assert time.monotonic() - started < 5
    assert len(bench.stub.state.log) == 1  # no model call after the cut


async def test_a_step_lost_to_a_deadlock_is_tried_once_more(bench: Bench) -> None:
    bench.stub.state.replies.extend([call("probe_conflict", label="once"), {"content": "Ok."}])
    run_id = (await bench.say("Do it"))["agent_run"]["id"]
    assert await bench.run_next() == StopReason.COMPLETED
    assert CONFLICTS[uuid.UUID(run_id)] == 2
    assert await probe_tools.effects(bench.session, uuid.UUID(run_id)) == ["once"]  # once
    events = await bench.session.scalars(
        select(RunEvent.seq).where(RunEvent.run_id == run_id, RunEvent.kind != EventKind.STOP)
    )
    assert sorted(events) == [1, 2, 3]  # the journal counts on without a gap


async def test_a_step_lost_to_a_deadlock_twice_ends_the_run(bench: Bench) -> None:
    bench.stub.state.replies.extend([call("probe_conflict", label="always"), {"content": "-"}])
    run_id = (await bench.say("Do it"))["agent_run"]["id"]
    assert await bench.run_next() == StopReason.ERROR
    assert CONFLICTS[uuid.UUID(run_id)] == 2
    assert await probe_tools.effects(bench.session, uuid.UUID(run_id)) == []


async def _run(real_db: RealDb, run_id: uuid.UUID) -> Run:
    async with real_db.database.session_factory() as session:
        run = await session.get(Run, run_id)
        assert run is not None
        return run
