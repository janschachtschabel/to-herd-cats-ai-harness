"""Ruling for plan M6 task 9: "one open run" counts per thread in a channel (the thread
of the mentioning message), per conversation in a DM, a page thread and a ticket
thread (one per ticket). A run waiting for a release in one thread of a channel does
not hold the others; resuming it drops no other thread's run."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.models_base import utcnow
from app.core.permissions import SpaceRole
from app.modules.agents.control import resume_waiting
from app.modules.agents.executor_repository import claim
from app.modules.agents.models import Run, RunState
from app.modules.agents.run_repository import RunRepository
from tests.factories_agents import LEASE, make_agent
from tests.factories_messaging import post
from tests.factories_wiki import new_page, publish
from tests.factories_writing import Work


async def _channel(work: Work) -> str:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _mention(
    work: Work, conversation: str, text: str, parent_id: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"body_md": text, "mentions": [str(work.bench.agent.id)]}
    if parent_id is not None:
        body["parent_id"] = parent_id
    r = await work.bench.people.alice.post(f"/api/conversations/{conversation}/messages", json=body)
    assert r.status_code == 201, r.text
    written: dict[str, Any] = r.json()
    return written


async def _wait(work: Work, run_id: str) -> Run:
    """The run waits for a release (as the approval gate leaves it)."""
    run = await work.bench.run_of(uuid.UUID(run_id))
    run.state, run.wait_until = RunState.WAITING, utcnow() + timedelta(hours=1)
    await work.bench.session.flush()
    return run


async def _states(work: Work) -> dict[uuid.UUID, str]:
    rows = await work.bench.session.scalars(select(Run).execution_options(populate_existing=True))
    return {run.id: run.state for run in rows}


async def test_a_waiting_run_holds_its_thread_only(work: Work) -> None:
    channel = await _channel(work)
    first = await _mention(work, channel, "@Ava eins")
    waiting = await _wait(work, first["agent_run"]["id"])
    same = await _mention(work, channel, "@Ava noch was", parent_id=first["id"])
    assert same["agent_run"]["id"] is None and same["agent_run"]["reason"] == "run.waiting"
    other = await _mention(work, channel, "@Ava zwei")
    assert other["agent_run"]["reason"] is None
    started = await work.bench.run_of(uuid.UUID(other["agent_run"]["id"]))
    assert started.lane_id == uuid.UUID(other["id"])
    assert waiting.lane_id == uuid.UUID(first["id"])
    async with work.bench.unit()() as session:
        claimed = await claim(session, LEASE)
    assert claimed is not None and claimed.id == started.id  # not held by the waiting run


async def test_two_threads_of_a_channel_run_at_once(work: Work) -> None:
    channel = await _channel(work)
    one = await _mention(work, channel, "@Ava eins")
    two = await _mention(work, channel, "@Ava zwei")
    root = await post(work.bench.people.admin, channel, "Frage")
    three = await _mention(work, channel, "@Ava drei", parent_id=root["id"])
    ids = {uuid.UUID(m["agent_run"]["id"]) for m in (one, two, three)}
    assert len(ids) == 3
    claimed = set()
    for _ in ids:
        async with work.bench.unit()() as session:
            found = await claim(session, LEASE)
        assert found is not None
        claimed.add(found.id)
    assert claimed == ids
    assert set((await _states(work)).values()) == {RunState.RUNNING}


async def test_resuming_a_thread_drops_no_other_threads_run(work: Work) -> None:
    channel = await _channel(work)
    first = await _mention(work, channel, "@Ava eins")
    await _wait(work, first["agent_run"]["id"])
    other = await _mention(work, channel, "@Ava zwei")  # queued, never started
    assert await resume_waiting(work.bench.session, work.space.org_id, first["agent_run"]["id"])
    states = await _states(work)
    assert states[uuid.UUID(first["agent_run"]["id"])] == RunState.QUEUED
    assert states[uuid.UUID(other["agent_run"]["id"])] == RunState.QUEUED


async def test_a_page_thread_keeps_one_run_for_the_whole_page(work: Work) -> None:
    page = await publish(work.admin, await new_page(work.admin, work.space.id, "Regeln"))
    thread = (await work.admin.get(f"/api/pages/{page['id']}/thread")).json()["id"]
    first = await _mention(work, thread, "@Ava eins")
    assert first["agent_run"]["id"] is not None
    run = await work.bench.run_of(uuid.UUID(first["agent_run"]["id"]))
    assert run.lane_id is None  # the conversation is its lane
    other = await _mention(work, thread, "@Ava zwei")
    assert other["agent_run"]["reason"] == "run.waiting"


async def test_a_dm_keeps_one_run_for_the_conversation(work: Work) -> None:
    posted = await work.bench.say("Hallo")
    run = await work.bench.run_of(uuid.UUID(posted["agent_run"]["id"]))
    assert run.lane_id is None
    await _wait(work, posted["agent_run"]["id"])
    again = await work.bench.say("Und?")
    assert again["agent_run"]["reason"] == "run.waiting"


async def test_resuming_keeps_the_run_a_handover_queued_behind_it(work: Work) -> None:
    """A ticket handed over while its run went on queues the next agent's run behind
    it in the same lane; the first run's resume must not drop it."""
    await work.bench.join(work.space, SpaceRole.EDITOR)
    ticket = await work.ticket()
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}",
        json={
            "version": ticket["version"],
            "assignee": {"type": "agent", "id": str(work.bench.agent.id)},
        },
    )
    assert r.status_code == 200, r.text
    first = (await work.bench.session.scalars(select(Run))).one()
    first.state, first.wait_until = RunState.WAITING, utcnow() + timedelta(hours=1)
    await work.bench.session.flush()
    runs = RunRepository(work.bench.session, work.space.org_id)
    bert = await make_agent(
        work.bench.session, work.bench.people, work.bench.connection.id, name="Bert"
    )
    follows = await runs.start(
        bert.id,
        first.user_id,
        first.conversation_id,
        work_item_id=first.work_item_id,
        chain_depth=1,
        besides=first.id,
    )
    assert follows is not None
    assert await resume_waiting(work.bench.session, work.space.org_id, first.id)
    states = await _states(work)
    assert (states[first.id], states[follows]) == (RunState.QUEUED, RunState.QUEUED)
