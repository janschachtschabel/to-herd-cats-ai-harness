"""Plan M6 task 1: a run taken up again goes on from its journal. A worker dies (here:
an exception no one catches, after or inside a step's transaction); the next take-up
replays the recorded model answers and tool results without calling the provider or
running the tool again, and goes on after the last recorded step. A writing tool's
effect and its journal entry are committed together. (With a real process killed:
`test_run_crash.py`.)"""

import json
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.core.models_base import utcnow
from app.modules.agents.executor_repository import RunSteps, claim
from app.modules.agents.run_models import EventKind, Run, RunEvent, StopReason
from app.modules.agents.step_host import RunHost
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.ai.models import AiPolicy
from tests.factories_agents import LEASE, Bench
from tests.factories_spaces import MakeSpace
from tests.support import probe_tools
from tests.support.probe_tools import count, effects
from tests.test_run_policy import SECRET, space_with_page


class Crash(BaseException):
    """The worker dies here: nothing after this point of the take-up happens."""


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


def die_after(monkeypatch: pytest.MonkeyPatch, method: str, step: int = 1) -> None:
    """The worker dies right after `RunHost.<method>` of `step` committed."""
    original = getattr(RunHost, method)

    async def dying(self: RunHost, at: int, *args: Any) -> Any:
        result = await original(self, at, *args)
        if at == step:
            raise Crash
        return result

    monkeypatch.setattr(RunHost, method, dying)


async def take_up_again(bench: Bench) -> StopReason | None:
    """The dead worker's lease runs out; another worker takes the run up."""
    for run in await bench.session.scalars(select(Run)):
        if run.lease_until is not None:
            run.lease_until = utcnow() - timedelta(seconds=1)
    await bench.session.flush()
    return await bench.run_next()


async def journal(bench: Bench) -> list[tuple[int, int, str]]:
    rows = await bench.session.scalars(select(RunEvent).order_by(RunEvent.seq))
    return [(e.seq, e.attempt, e.kind) for e in rows]


@pytest.fixture(autouse=True)
def _probes(monkeypatch: pytest.MonkeyPatch) -> None:
    probe_tools.installed(monkeypatch)


async def test_a_run_goes_on_after_its_last_recorded_step(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench.stub.state.replies.extend([call("probe_write", label="a"), {"content": "Done."}])
    posted = await bench.say("Write it")
    die_after(monkeypatch, "call_tool")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    probe_tools.installed(monkeypatch)
    assert await effects(bench.session) == ["a"]
    assert await take_up_again(bench) == StopReason.COMPLETED
    assert await effects(bench.session) == ["a"]  # the tool did not run again
    assert len(bench.stub.state.log) == 2  # step 1 before the crash, step 2 after: none twice
    second = json.dumps(bench.stub.state.log[1].body["messages"])
    assert "wrote a" in second and "probe_write" in second  # the replayed step, as history
    answers = [m for m in await bench.messages() if m["kind"] == "agent"]
    assert [a["body_md"] for a in answers] == ["Done."]
    assert await journal(bench) == [
        (0, 2, "stop"),
        (1, 1, "model_call"),
        (2, 1, "tool_call"),
        (3, 2, "model_call"),
    ]
    run = await bench.run_of(posted["agent_run"]["id"])
    assert (run.attempt, run.recoveries, run.steps) == (2, 1, 2)


async def test_a_recorded_call_without_its_result_runs_once(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker died after recording the model's answer, before its tool ran."""
    bench.stub.state.replies.extend([call("probe_write", label="b"), {"content": "Done."}])
    await bench.say("Write it")
    die_after(monkeypatch, "after_model_call")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    probe_tools.installed(monkeypatch)
    assert await effects(bench.session) == []
    assert await take_up_again(bench) == StopReason.COMPLETED
    assert await effects(bench.session) == ["b"]
    assert len(bench.stub.state.log) == 2


async def test_a_worker_dying_inside_the_tool_leaves_no_effect(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Effect written, transaction not committed: gone with the worker, done once by
    the next take-up."""
    real = probe_tools.probe_write
    dies = [True]

    async def dying(ctx: Any, args: Any) -> Any:
        result = await real(ctx, args)
        if dies.pop() if dies else False:
            raise Crash
        return result

    monkeypatch.setitem(CATALOG, "probe_write", replace(probe_tools.PROBES[0], run=dying))
    bench.stub.state.replies.extend([call("probe_write", label="c"), {"content": "Done."}])
    await bench.say("Write it")
    with pytest.raises(Crash):
        await bench.run_next()
    assert await effects(bench.session) == []
    assert await count(bench.session, RunEvent, RunEvent.kind == EventKind.TOOL_CALL) == 0
    assert await take_up_again(bench) == StopReason.COMPLETED
    assert await effects(bench.session) == ["c"]


async def test_an_effect_whose_entry_cannot_be_written_is_undone(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = RunSteps.event

    async def failing(self: RunSteps, seq: int, kind: EventKind, content: Any) -> None:
        if kind == EventKind.TOOL_CALL:
            raise RuntimeError("cannot store")
        await original(self, seq, kind, content)

    monkeypatch.setattr(RunSteps, "event", failing)
    bench.stub.state.replies.extend([call("probe_write", label="d"), {"content": "never"}])
    await bench.say("Write it")
    assert await bench.run_next() == StopReason.ERROR
    assert await effects(bench.session) == []  # one transaction: no entry, no effect


async def test_an_answer_recorded_before_the_end_is_not_asked_again(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench.stub.state.replies.append({"content": "Recorded answer."})
    await bench.say("Hi")
    die_after(monkeypatch, "after_model_call")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    assert await take_up_again(bench) == StopReason.COMPLETED
    assert len(bench.stub.state.log) == 1
    answers = [m["body_md"] for m in await bench.messages() if m["kind"] == "agent"]
    assert answers == ["Recorded answer."]


async def test_what_the_journal_read_counts_before_the_next_call(
    bench: Bench, make_space: MakeSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The replayed history goes to the provider with the next call: what it had read
    counts for the policy check before it, as if the run had never stopped."""
    await bench.locate("eu")
    _, page = await space_with_page(bench, make_space, AiPolicy.RESTRICTED, ["eu"])
    bench.stub.state.replies.extend([call("read_page", page_id=page["id"]), {"content": "x"}])
    await bench.say("Read it")
    die_after(monkeypatch, "call_tool")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    await bench.locate("external")  # the connection may no longer receive that space
    assert await take_up_again(bench) == StopReason.POLICY_BLOCKED
    assert len(bench.stub.state.log) == 1 and SECRET not in bench.stub.state.texts()


async def test_the_recovery_limit_counts_only_lost_leases(bench: Bench) -> None:
    """Take-ups after a wait are no recoveries; three take-ups after dead workers are."""
    posted = await bench.say("Hi")
    run = await bench.run_of(posted["agent_run"]["id"])
    run.attempt = 5  # four earlier take-ups, all after waits
    await bench.session.flush()
    assert await bench.run_next() == StopReason.COMPLETED
    async with bench.unit()() as session:
        assert await claim(session, LEASE) is None
