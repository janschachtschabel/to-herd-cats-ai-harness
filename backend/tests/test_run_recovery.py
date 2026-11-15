"""Review Focus 7 and the executor's limits: a worker that dies or hangs mid-run, a
second worker, a message sent twice: one run, one answer, each model call's usage
once. Also the lease, the attempt limit, `max_concurrency`, `requests_per_minute`
and the deadline."""

import time
import uuid
from datetime import timedelta
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import func, select

from app.core.models_base import utcnow
from app.modules.agents.executor import MAX_RECOVERIES, Executor
from app.modules.agents.executor_repository import Claimed, RunSteps, claim
from app.modules.agents.run_models import EventKind, Run, RunEvent, RunState, StopReason
from app.modules.ai.models import UsageRecord
from app.modules.messaging.models import Message, MessageKind
from app.runtime.models import BuiltModel, ModelTarget, wrap_model
from tests.factories_agents import Bench, make_agent, open_agent_dm


async def _claim(bench: Bench, lease: float = 30) -> Claimed | None:
    async with bench.unit()() as session:
        return await claim(session, lease)


async def _expire(bench: Bench, run_id: uuid.UUID) -> None:
    run = await bench.run_of(run_id)
    run.lease_until = utcnow() - timedelta(seconds=1)
    await bench.session.flush()


async def _count(bench: Bench, model: Any, *where: Any) -> int:
    return int(await bench.session.scalar(select(func.count()).select_from(model).where(*where)))


async def test_a_dead_workers_run_is_taken_over_and_answered_once(bench: Bench) -> None:
    """Worker A records one step and dies (its lease runs out); worker B starts the run
    again and answers; A wakes up and writes nothing more."""
    await bench.say("Hi")
    first = await _claim(bench)
    assert first is not None
    taken: list[Claimed] = []

    async def worker_a(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart("search", {"query": "x"})])
        await _expire(bench, first.id)  # A hung past its lease ...
        second = await _claim(bench)  # ... and B took the run over
        assert second is not None and second.id == first.id and second.attempt == 2
        taken.append(second)
        return ModelResponse(parts=[TextPart("A's late answer")])

    a = bench.executor(make_model=lambda t, s: wrap_model(FunctionModel(worker_a)))
    assert await a.execute(first) is None  # lost: nothing written
    bench.stub.state.replies.append({"content": "B's answer"})
    assert await bench.executor().execute(taken[0]) == StopReason.COMPLETED
    answers = (
        await bench.session.scalars(
            select(Message.body_md).where(Message.kind == MessageKind.AGENT)
        )
    ).all()
    assert answers == ["B's answer"]
    calls = await _count(bench, RunEvent, RunEvent.kind == EventKind.MODEL_CALL)
    assert calls == 2  # A's first call and B's call; A's second was never recorded
    assert await _count(bench, UsageRecord) == calls
    run = await bench.run_of(first.id)
    assert (run.state, run.attempt, run.steps) == ("done", 2, 2)


async def test_a_second_write_of_a_step_is_refused(bench: Bench) -> None:
    await bench.say("Hi")
    claimed = await _claim(bench)
    assert claimed is not None
    async with bench.unit()() as session:
        await RunSteps(session, claimed).event(1, EventKind.MODEL_CALL, {})
    try:
        async with bench.unit()() as session:
            await RunSteps(session, claimed).event(1, EventKind.MODEL_CALL, {})
    except Exception as exc:  # noqa: BLE001
        assert "IntegrityError" in type(exc).__name__
    else:
        raise AssertionError("the same step was recorded twice")


async def test_a_resent_message_starts_no_second_run(bench: Bench) -> None:
    key = str(uuid.uuid4())
    body = {"body_md": "Hi", "client_id": key}
    url = f"/api/conversations/{bench.dm_id}/messages"
    first = (await bench.people.alice.post(url, json=body)).json()
    again = await bench.people.alice.post(url, json=body)
    assert again.status_code in (200, 201)
    assert first["agent_run"]["id"] is not None
    assert await _count(bench, Run) == 1
    assert await bench.run_next() == StopReason.COMPLETED
    assert await _claim(bench) is None


async def test_one_run_per_conversation_and_two_workers(bench: Bench) -> None:
    await bench.say("Hi")
    claimed = await _claim(bench)
    assert claimed is not None
    await bench.say("More")  # queued behind the running one
    assert await _claim(bench) is None  # the conversation is busy
    await _expire(bench, claimed.id)
    again = await _claim(bench)
    assert again is not None and again.id == claimed.id  # the stale one first


async def test_max_concurrency_per_connection(bench: Bench) -> None:
    bench.connection.max_concurrency = 1
    await bench.session.flush()
    bob_dm = await open_agent_dm(bench.people.bob, bench.agent)
    await bench.say("Hi")
    await bench.say("Hi", who="bob", dm=str(bob_dm["id"]))
    first = await _claim(bench)
    assert first is not None
    assert await _claim(bench) is None  # the connection's one place is taken
    bench.connection.max_concurrency = 2
    await bench.session.flush()
    second = await _claim(bench)
    assert second is not None and second.conversation_id != first.conversation_id


async def test_runs_of_other_connections_do_not_count(bench: Bench) -> None:
    bench.connection.max_concurrency = 1
    await bench.session.flush()
    await bench.say("Hi")
    assert await _claim(bench) is not None
    other = await make_agent(bench.session, bench.people, bench.connection.id, name="Bo")
    bob_dm = await open_agent_dm(bench.people.bob, other)
    await bench.say("Hi", who="bob", dm=str(bob_dm["id"]))
    assert await _claim(bench) is None  # same connection, also another agent


async def test_requests_per_minute(bench: Bench) -> None:
    await bench.say("Hi")
    claimed = await _claim(bench)
    assert claimed is not None
    async with bench.unit()() as session:
        steps = RunSteps(session, claimed)
        assert await steps.take_rate(bench.connection.id, 2) == 0
        assert await steps.take_rate(bench.connection.id, 2) == 0
        wait = await steps.take_rate(bench.connection.id, 2)
    assert 0 < wait <= 60


async def test_a_full_rate_window_waits_into_the_deadline(bench: Bench) -> None:
    bench.connection.requests_per_minute = 1
    bench.agent.max_runtime_seconds = 10
    await bench.session.flush()
    bench.stub.state.replies.extend(
        [{"tool_calls": [{"name": "search", "arguments": {"query": "x"}}]}, {"content": "-"}]
    )
    await bench.say("Hi")
    assert await bench.run_next() == StopReason.DEADLINE  # the window outlasts the run
    assert len(bench.stub.state.log) == 1


class Skewed:
    """A clock that jumps ahead once the model is made (after the run's deadline is
    set), so a run of 10 seconds has `left` seconds left."""

    def __init__(self, left: float, runtime: float) -> None:
        self.skew = 0.0
        self.jump = runtime - left

    def __call__(self) -> float:
        return time.monotonic() + self.skew


async def test_the_deadline_cuts_a_stuck_call(bench: Bench) -> None:
    bench.agent.max_runtime_seconds = 10
    await bench.session.flush()
    clock = Skewed(left=0.5, runtime=10)
    real = bench.make_model

    def make_model(target: ModelTarget, timeout: float) -> BuiltModel:
        clock.skew = clock.jump
        return real(target, timeout)

    bench.stub.state.delay = 5
    await bench.say("Hi")
    started = time.monotonic()
    executor = Executor(bench.unit(), make_model=make_model, clock=clock)
    assert await bench.run_next(executor) == StopReason.DEADLINE
    assert time.monotonic() - started < 3
    notice = [m for m in await bench.messages() if m["kind"] == "system"]
    assert notice[0]["system"]["new"]["value"] == "deadline"


async def test_a_run_whose_workers_keep_dying_ends(bench: Bench) -> None:
    posted = await bench.say("Hi")
    run = await bench.run_of(posted["agent_run"]["id"])
    run.state, run.attempt, run.started_at = RunState.RUNNING, MAX_RECOVERIES + 1, utcnow()
    run.recoveries = MAX_RECOVERIES  # the next take-up after a lost lease is one too many
    run.lease_until = utcnow() - timedelta(seconds=1)
    await bench.session.flush()
    assert await bench.run_next() == StopReason.ERROR
    stop = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.STOP))
    assert stop is not None and stop.content == {"reason": "error", "detail": "attempts"}
    assert bench.stub.state.log == []


async def test_a_lost_lease_cancels_nothing_written(bench: Bench) -> None:
    """Renewal keeps the lease only for the attempt that holds it."""
    from app.modules.agents.executor_repository import renew

    await bench.say("Hi")
    claimed = await _claim(bench, lease=5)
    assert claimed is not None
    async with bench.unit()() as session:
        assert await renew(session, {claimed.id: claimed.attempt}, 30) == {claimed.id}
        assert await renew(session, {claimed.id: claimed.attempt + 1}, 30) == set()
    run = await bench.run_of(claimed.id)
    assert run.lease_until is not None and run.lease_until > utcnow() + timedelta(seconds=20)
