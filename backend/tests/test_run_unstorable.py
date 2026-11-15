"""Module review 1, finding 2: what the database cannot store (NUL, lone surrogates)
never makes a run retry blind, and a step whose record fails ends the run at once:
one provider call, its usage recorded, stop `error`."""

import dataclasses
from typing import Any

import pytest
from sqlalchemy import func, select

from app.modules.agents.executor_repository import RunSteps
from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.ai.models import UsageRecord
from tests.factories_agents import Bench


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


async def usage_rows(bench: Bench) -> int:
    return int(await bench.session.scalar(select(func.count()).select_from(UsageRecord)) or 0)


async def stop_detail(bench: Bench) -> object:
    stop = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.STOP))
    assert stop is not None
    return stop.content["detail"]


async def test_an_answer_with_nul_is_stored_without_it(bench: Bench) -> None:
    bench.stub.state.replies.append({"content": "a\u0000b"})
    await bench.say("Hi")
    assert await bench.run_next() == StopReason.COMPLETED
    answers = [m["body_md"] for m in await bench.messages() if m["kind"] == "agent"]
    assert answers == ["ab"]
    assert len(bench.stub.state.log) == 1 and await usage_rows(bench) == 1


async def test_tool_arguments_with_nul_do_not_break_the_step(bench: Bench) -> None:
    bench.stub.state.replies.extend([call("search", query="a\u0000b"), {"content": "ok"}])
    await bench.say("Find")
    assert await bench.run_next() == StopReason.COMPLETED
    tool = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.TOOL_CALL))
    assert tool is not None and tool.content["args"] == {"query": "ab"}
    assert len(bench.stub.state.log) == 2 and await usage_rows(bench) == 2


async def test_a_step_whose_record_fails_ends_the_run_at_once(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = RunSteps.event

    async def failing(self: RunSteps, seq: int, kind: EventKind, content: Any) -> None:
        if kind == EventKind.MODEL_CALL:
            raise RuntimeError("cannot store")
        await original(self, seq, kind, content)

    monkeypatch.setattr(RunSteps, "event", failing)
    bench.stub.state.replies.extend([{"content": "one"}, {"content": "two"}])
    await bench.say("Hi")
    assert await bench.run_next() == StopReason.ERROR
    assert len(bench.stub.state.log) == 1  # no second, blind call
    assert await usage_rows(bench) == 1  # the call is still counted
    assert await stop_detail(bench) == "RuntimeError"
    assert [m for m in await bench.messages() if m["kind"] == "agent"] == []


async def test_a_tool_that_fails_ends_the_run_at_once(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(ctx: Any, args: Any) -> Any:
        raise ValueError("broken")

    monkeypatch.setitem(CATALOG, "search", dataclasses.replace(CATALOG["search"], run=failing))
    bench.stub.state.replies.extend([call("search", query="x"), {"content": "never"}])
    await bench.say("Find")
    assert await bench.run_next() == StopReason.ERROR
    assert len(bench.stub.state.log) == 1 and await usage_rows(bench) == 1
    assert await stop_detail(bench) == "ValueError"
