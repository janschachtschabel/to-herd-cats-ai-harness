"""Plan M6 task 1: a run that waits for a person holds nothing, keeps its conversation
(a message meanwhile starts no run: `run.waiting`), goes on from its journal once
resumed, ends with `waiting_timeout` when nobody answers in time, and stops on a
cancel request (`cancelled`), checked before every step and when it ends."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.core.models_base import utcnow
from app.modules.agents import control
from app.modules.agents.executor_repository import claim, open_runs
from app.modules.agents.models import EventKind, Run, RunEvent, RunState, StopReason
from app.modules.agents.step_host import RunHost
from app.worker.runs import run_metrics
from tests.factories_agents import LEASE, Bench
from tests.support import probe_tools
from tests.support.probe_tools import ANSWERED, WAIT_HOURS


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


@pytest.fixture(autouse=True)
def _probes(monkeypatch: pytest.MonkeyPatch) -> None:
    probe_tools.installed(monkeypatch)
    ANSWERED.clear()


async def waiting_run(bench: Bench) -> Run:
    """A run that asked with `probe_wait` and now waits."""
    bench.stub.state.replies.extend([call("probe_wait", label="ok?"), {"content": "Thanks."}])
    posted = await bench.say("Do it")
    assert await bench.run_next() is None  # not done: waiting
    return await bench.run_of(posted["agent_run"]["id"])


async def stop_of(bench: Bench, run: Run) -> dict[str, Any]:
    stmt = select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.kind == EventKind.STOP)
    event = await bench.session.scalar(stmt)
    assert event is not None
    return event.content


async def notices(bench: Bench) -> list[str]:
    return [m["system"]["new"]["value"] for m in await bench.messages() if m["kind"] == "system"]


async def test_a_waiting_run_holds_nothing_and_keeps_its_conversation(bench: Bench) -> None:
    run = await waiting_run(bench)
    assert (run.state, run.lease_until) == ("waiting", None)
    assert run.wait_until is not None
    assert run.wait_until - utcnow() > timedelta(hours=WAIT_HOURS - 1)
    tools = await bench.session.scalars(select(RunEvent.kind).where(RunEvent.run_id == run.id))
    assert list(tools) == ["model_call"]  # the waiting call has no result yet
    async with bench.unit()() as session:
        assert await claim(session, LEASE) is None
        assert (await open_runs(session)).waiting == 1
    later = await bench.say("Anything?")
    assert later["agent_run"] == {"id": None, "reason": "run.waiting"}
    shown = await bench.people.alice.get(f"/api/runs/{run.id}")
    assert shown.json()["state"] == "waiting" and shown.json()["wait_until"] is not None


async def test_a_resumed_run_runs_the_waiting_call_again_and_nothing_before(
    bench: Bench,
) -> None:
    run = await waiting_run(bench)
    ANSWERED.add(run.id)
    async with bench.unit()() as session:
        assert await control.resume_waiting(session, run.org_id, run.id)
        assert not await control.resume_waiting(session, run.org_id, run.id)  # once
    assert (await bench.run_of(run.id)).state == RunState.QUEUED
    assert await bench.run_next() == StopReason.COMPLETED
    assert len(bench.stub.state.log) == 2  # step 1 once, before the wait; step 2 after
    tool = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.TOOL_CALL))
    assert tool is not None and tool.content["text"] == "answered ok?"
    done = await bench.run_of(run.id)
    assert (done.attempt, done.recoveries, done.wait_until) == (2, 0, None)
    assert [m["body_md"] for m in await bench.messages() if m["kind"] == "agent"] == ["Thanks."]


async def test_what_came_in_while_it_waited_is_answered_after_it(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A message during the running step queues a run behind it; the run then waits,
    is resumed (the queued one, never started, is dropped) and when it ends it queues
    a run for that message, which is answered next."""
    bench.stub.state.replies.extend(
        [call("probe_wait", label="ok?"), {"content": "Thanks."}, {"content": "Second."}]
    )
    first = await bench.say("Do it")
    original = RunHost.call_tool

    async def meanwhile(self: RunHost, step: int, *args: Any) -> Any:
        await bench.say("And this?")  # queued behind the running run
        return await original(self, step, *args)

    monkeypatch.setattr(RunHost, "call_tool", meanwhile)
    assert await bench.run_next() is None
    monkeypatch.undo()
    probe_tools.installed(monkeypatch)
    queued = await bench.session.scalars(select(Run).where(Run.state == RunState.QUEUED))
    assert len(list(queued)) == 1
    async with bench.unit()() as session:
        assert await claim(session, LEASE) is None  # the waiting run keeps the conversation
    run_id = uuid.UUID(first["agent_run"]["id"])
    ANSWERED.add(run_id)
    async with bench.unit()() as session:
        assert await control.resume_waiting(session, bench.agent.org_id, run_id)
    assert await bench.run_next() == StopReason.COMPLETED
    assert await bench.run_next() == StopReason.COMPLETED  # the follow-up
    answers = [m["body_md"] for m in await bench.messages() if m["kind"] == "agent"]
    assert answers == ["Thanks.", "Second."]
    assert "And this?" in bench.stub.state.texts()


async def test_nobody_answers_in_time(bench: Bench) -> None:
    run = await waiting_run(bench)
    async with bench.unit()() as session:
        assert await control.sweep_waiting(session) == 0  # not yet
    run.wait_until = utcnow() - timedelta(seconds=1)
    await bench.session.flush()
    async with bench.unit()() as session:
        assert await control.sweep_waiting(session) == 1
    done = await bench.run_of(run.id)
    assert (done.state, done.stop_reason, done.wait_until) == ("done", "waiting_timeout", None)
    assert await stop_of(bench, done) == {"reason": "waiting_timeout", "detail": None}
    assert await notices(bench) == ["waiting_timeout"]
    async with bench.unit()() as session:
        assert not await control.resume_waiting(session, run.org_id, run.id)


async def test_a_waiting_run_asked_to_stop_ends_at_the_next_sweep(bench: Bench) -> None:
    run = await waiting_run(bench)
    alice = bench.people.users["alice"]
    async with bench.unit()() as session:
        assert await control.request_cancel(session, run.org_id, run.id, alice.id)
        assert await control.request_cancel(session, run.org_id, run.id, alice.id)  # kept once
        assert await control.sweep_waiting(session) == 1
    done = await bench.run_of(run.id)
    assert done.stop_reason == StopReason.CANCELLED
    assert await stop_of(bench, done) == {
        "reason": "cancelled",
        "detail": None,
        "by": str(alice.id),
    }
    assert await notices(bench) == ["cancelled"]
    async with bench.unit()() as session:
        assert not await control.request_cancel(session, run.org_id, run.id, alice.id)  # done


async def test_a_running_run_stops_before_its_next_step(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench.stub.state.replies.extend([call("search", query="x"), {"content": "never"}])
    posted = await bench.say("Find")
    alice = bench.people.users["alice"]
    original = RunHost.after_model_call

    async def asked(self: RunHost, step: int, reply: Any) -> None:
        await original(self, step, reply)
        async with bench.unit()() as session:
            await control.request_cancel(session, bench.agent.org_id, self.run.claimed.id, alice.id)

    monkeypatch.setattr(RunHost, "after_model_call", asked)
    assert await bench.run_next() == StopReason.CANCELLED
    assert len(bench.stub.state.log) == 1
    kinds = await bench.session.scalars(
        select(RunEvent.kind).where(RunEvent.run_id == posted["agent_run"]["id"])
    )
    assert sorted(kinds) == ["model_call", "stop"]  # the search never ran
    assert await notices(bench) == ["cancelled"]


async def test_a_cancel_request_wins_over_the_answer(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asked while the last model call was on its way: the end checks once more, in
    its own transaction, and writes no answer."""
    bench.stub.state.replies.append({"content": "Too late."})
    await bench.say("Hi")
    alice = bench.people.users["alice"]
    original = RunHost.after_model_call

    async def asked(self: RunHost, step: int, reply: Any) -> None:
        await original(self, step, reply)
        async with bench.unit()() as session:
            await control.request_cancel(session, bench.agent.org_id, self.run.claimed.id, alice.id)

    monkeypatch.setattr(RunHost, "after_model_call", asked)
    assert await bench.run_next() == StopReason.CANCELLED
    assert [m for m in await bench.messages() if m["kind"] == "agent"] == []


async def test_a_queued_run_asked_to_stop_never_calls(bench: Bench) -> None:
    posted = await bench.say("Hi")
    alice = bench.people.users["alice"]
    async with bench.unit()() as session:
        org = bench.agent.org_id
        assert await control.request_cancel(session, org, posted["agent_run"]["id"], alice.id)
    assert await bench.run_next() == StopReason.CANCELLED
    assert bench.stub.state.log == []


async def test_the_run_loop_sweeps_and_counts_waiting_runs(bench: Bench) -> None:
    run = await waiting_run(bench)
    metrics = run_metrics()
    async with bench.unit()() as session:
        metrics.waiting.set((await open_runs(session)).waiting)
    assert metrics.waiting._value.get() == 1  # noqa: SLF001
    run.wait_until = utcnow() - timedelta(seconds=1)
    await bench.session.flush()
    async with bench.unit()() as session:
        assert await control.sweep_waiting(session) == 1
        assert (await open_runs(session)).waiting == 0
