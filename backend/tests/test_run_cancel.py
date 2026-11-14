"""Cancelling a run (plan M6 decision 12, task 10): `POST /api/runs/{id}/cancel` for the
asking person, the agent's responsible person and `agent.manage` (whoever sees the
run). It writes the cancel request once; a queued or waiting run ends at once as
`cancelled`, a running one before its next step. A cancelled run posts its notice
like other stops and writes nothing else: no answer, no run for what came meanwhile.
A finished run answers 409 `run.finished`; asking twice answers the same way."""

from typing import Any

import pytest
from sqlalchemy import func, select

from app.modules.agents.executor_repository import claim
from app.modules.agents.models import EventKind, Run, RunCancelRequest, RunEvent, RunState
from app.modules.agents.models import StopReason as Stop
from tests.factories_agents import LEASE, Bench
from tests.support import probe_tools
from tests.support.probe_tools import ANSWERED


@pytest.fixture(autouse=True)
def _probes(monkeypatch: pytest.MonkeyPatch) -> None:
    probe_tools.installed(monkeypatch)
    ANSWERED.clear()


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


async def cancel(bench: Bench, run_id: object, who: str = "alice") -> Any:
    return await getattr(bench.people, who).post(f"/api/runs/{run_id}/cancel")


async def notices(bench: Bench) -> list[str]:
    return [m["system"]["new"]["value"] for m in await bench.messages() if m["kind"] == "system"]


async def runs_of(bench: Bench) -> list[Run]:
    stmt = select(Run).where(Run.conversation_id == bench.dm["id"]).order_by(Run.id)
    return list(await bench.session.scalars(stmt.execution_options(populate_existing=True)))


async def stop_event(bench: Bench, run_id: object) -> dict[str, Any]:
    stmt = select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.kind == EventKind.STOP)
    found = await bench.session.scalar(stmt)
    assert found is not None
    return found.content


async def test_a_queued_run_ends_at_once_and_twice_answers_the_same(bench: Bench) -> None:
    posted = await bench.say("Hi")
    await bench.say("And more")  # the same queued run would answer it
    run_id = posted["agent_run"]["id"]
    first = await cancel(bench, run_id)
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["state"], body["stop_reason"], body["cancel_requested"]) == (
        "done",
        "cancelled",
        True,
    )
    again = await cancel(bench, run_id)
    assert again.status_code == 200 and again.json() == body
    assert await notices(bench) == ["cancelled"]
    stop = await stop_event(bench, run_id)
    assert stop == {"reason": "cancelled", "detail": None, "by": bench.people.id("alice")}
    assert [r.state for r in await runs_of(bench)] == [RunState.DONE]  # no follow-up
    async with bench.unit()() as session:
        assert await claim(session, LEASE) is None
    assert bench.stub.state.log == []
    requests = await bench.session.scalar(select(func.count()).select_from(RunCancelRequest))
    assert requests == 1


async def test_a_waiting_run_ends_at_once(bench: Bench) -> None:
    bench.stub.state.replies.append(call("probe_wait", label="ok?"))
    posted = await bench.say("Do it")
    assert await bench.run_next() is None
    meanwhile = await bench.say("Still there?")
    assert meanwhile["agent_run"]["reason"] == "run.waiting"
    r = await cancel(bench, posted["agent_run"]["id"])
    assert r.status_code == 200 and r.json()["stop_reason"] == "cancelled"
    assert r.json()["wait_until"] is None
    assert await notices(bench) == ["cancelled"]
    assert [r.state for r in await runs_of(bench)] == [RunState.DONE]  # nothing queued after
    assert [m for m in await bench.messages() if m["kind"] == "agent"] == []


async def test_a_running_run_stops_before_its_next_step(bench: Bench) -> None:
    posted = await bench.say("Find")
    async with bench.unit()() as session:
        claimed = await claim(session, LEASE)
    assert claimed is not None
    r = await cancel(bench, posted["agent_run"]["id"])
    assert r.status_code == 200
    assert (r.json()["state"], r.json()["cancel_requested"]) == ("running", True)
    assert await bench.executor().execute(claimed) == Stop.CANCELLED
    assert bench.stub.state.log == []
    assert await notices(bench) == ["cancelled"]
    again = await cancel(bench, posted["agent_run"]["id"])
    assert again.status_code == 200 and again.json()["stop_reason"] == "cancelled"


async def test_a_finished_run_answers_409(bench: Bench) -> None:
    posted = await bench.say("Hi")
    assert await bench.run_next() == Stop.COMPLETED
    r = await cancel(bench, posted["agent_run"]["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "run.finished"
    requests = await bench.session.scalar(select(func.count()).select_from(RunCancelRequest))
    assert requests == 0
    assert await notices(bench) == []


async def test_the_responsible_person_and_agent_manage_may_cancel(bench: Bench) -> None:
    bench.agent.responsible_user_id = bench.people.users["bob"].id
    await bench.session.flush()
    first = (await bench.say("One"))["agent_run"]["id"]
    assert (await cancel(bench, first, "bob")).status_code == 200
    second = (await bench.say("Two"))["agent_run"]["id"]
    assert (await cancel(bench, second, "admin")).status_code == 200
    stop = await stop_event(bench, second)
    assert stop["by"] == bench.people.id("admin")


async def test_others_get_404_and_change_nothing(bench: Bench) -> None:
    run_id = (await bench.say("Hi"))["agent_run"]["id"]
    for who in ("bob", "carol", "gast"):
        r = await cancel(bench, run_id, who)
        assert r.status_code == 404 and r.json()["error"]["code"] == "run.not_found"
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id('alice')}",
        json={"no_ai": True, "version": None},
    )
    assert r.status_code == 200
    assert (await cancel(bench, run_id)).status_code == 404  # the asker without ai.use
    requests = await bench.session.scalar(select(func.count()).select_from(RunCancelRequest))
    assert requests == 0
    assert (await runs_of(bench))[0].state == RunState.QUEUED
