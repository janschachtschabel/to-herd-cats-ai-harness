"""The run view (plan M6 decision 12, task 10): "my runs" (the runs I asked for) and an
agent's runs (its responsible person, `agent.manage`), each paged newest first with
filters; one run with what the view needs (agent and asker names, its place, state,
counters, cost and tokens from the usage records, whether a cancel was asked). A run
one may not see answers like none; lists filter in SQL with a fixed number of
statements whatever their length."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.agents.models import Run, RunState, StopReason
from app.modules.agents.run_repository import RunRepository
from app.modules.messaging.models import Message
from tests.factories_agents import Bench

RUNS = "/api/runs"


@contextmanager
def counting(session: AsyncSession) -> Iterator[list[str]]:
    sync_conn = session.sync_session.connection()
    statements: list[str] = []

    def _count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(sync_conn, "before_cursor_execute", _count)
    try:
        yield statements
    finally:
        event.remove(sync_conn, "before_cursor_execute", _count)


async def answered(bench: Bench, text: str = "Hi") -> str:
    """One finished run of Alice's (answered by the stub)."""
    posted = await bench.say(text)
    assert await bench.run_next() == StopReason.COMPLETED
    return str(posted["agent_run"]["id"])


async def listed(client: AsyncClient, path: str = RUNS, **params: Any) -> list[dict[str, Any]]:
    r = await client.get(path, params=params)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def extra_run(bench: Bench, *, state: str = "done", reason: str | None = "completed") -> Run:
    """A run row of Alice's in her DM, written directly (no worker needed)."""
    alice = bench.people.users["alice"]
    trigger = await bench.session.scalar(
        select(Message.id).where(Message.conversation_id == bench.dm["id"]).limit(1)
    )
    assert trigger is not None
    run = Run(
        org_id=bench.agent.org_id,
        agent_id=bench.agent.id,
        user_id=alice.id,
        conversation_id=bench.dm["id"],
        trigger_message_id=trigger,
        state=state,
        stop_reason=reason,
        attempt=1,
        steps=0,
        created_at=utcnow(),
        finished_at=utcnow() if state == "done" else None,
    )
    bench.session.add(run)
    await bench.session.flush()
    return run


async def test_my_runs_show_what_the_view_needs(bench: Bench) -> None:
    bench.connection.prices = {"m1": {"input": "1", "output": "2"}}
    await bench.session.flush()
    first = await answered(bench)
    second = await answered(bench, "Again")
    items = await listed(bench.people.alice)
    assert [i["id"] for i in items] == [second, first]  # newest first
    item = items[0]
    assert item["agent_name"] == "Ava" and item["agent_id"] == str(bench.agent.id)
    assert item["asker_id"] == bench.people.id("alice") and item["asker_name"] == "Alice"
    assert item["place"] == {
        "kind": "dm",
        "conversation_id": bench.dm_id,
        "space_id": None,
        "page_id": None,
        "ticket_number": None,
    }
    assert (item["state"], item["stop_reason"]) == ("done", "completed")
    assert (item["attempt"], item["recoveries"], item["steps"]) == (1, 0, 1)
    assert item["started_at"] and item["finished_at"] and item["wait_until"] is None
    usage = item["usage"]
    assert usage["calls"] == 1 and usage["tokens_in"] > 0 and usage["tokens_out"] > 0
    assert usage["cost"] is not None and float(usage["cost"]) > 0
    assert item["cancel_requested"] is False
    detail = await bench.people.alice.get(f"{RUNS}/{second}")
    assert detail.status_code == 200 and detail.json() == item


async def test_nobody_else_sees_my_runs(bench: Bench) -> None:
    run_id = await answered(bench)
    assert await listed(bench.people.bob) == []
    for who in ("bob", "carol"):
        r = await getattr(bench.people, who).get(f"{RUNS}/{run_id}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "run.not_found"
    gone = await bench.people.alice.get(f"{RUNS}/0190f0f0-0000-7000-8000-000000000000")
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "run.not_found"


async def test_without_ai_there_is_no_list_of_my_runs(bench: Bench) -> None:
    r = await bench.people.gast.get(RUNS)
    assert r.status_code == 404 and r.json()["error"]["code"] == "ai.not_found"
    assert (await bench.people.admin.get(RUNS)).status_code == 200  # agent.manage


async def test_my_runs_filter_by_agent_state_reason_and_time(bench: Bench) -> None:
    done = await answered(bench)
    queued = await bench.say("Later")
    queued_id = queued["agent_run"]["id"]
    alice = bench.people.alice
    assert [i["id"] for i in await listed(alice, state="queued")] == [queued_id]
    assert [i["id"] for i in await listed(alice, stop_reason="completed")] == [done]
    assert await listed(alice, stop_reason="cancelled") == []
    both = {done, queued_id}
    assert {i["id"] for i in await listed(alice, agent_id=str(bench.agent.id))} == both
    assert await listed(alice, agent_id="0190f0f0-0000-7000-8000-000000000000") == []
    hour = timedelta(hours=1)
    assert {i["id"] for i in await listed(alice, since=(utcnow() - hour).isoformat())} == both
    assert await listed(alice, since=(utcnow() + hour).isoformat()) == []
    assert await listed(alice, until=(utcnow() - hour).isoformat()) == []
    naive = await alice.get(RUNS, params={"since": "2026-01-01T00:00:00"})
    assert naive.status_code == 422


async def test_my_runs_page_by_cursor(bench: Bench) -> None:
    first = await answered(bench)
    runs = [await extra_run(bench) for _ in range(3)]
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        r = await bench.people.alice.get(RUNS, params=params)
        seen += [i["id"] for i in r.json()["items"]]
        if (cursor := r.json()["next_cursor"]) is None:
            break
    assert seen == [str(r.id) for r in reversed(runs)] + [first]


async def test_a_run_started_by_a_trigger_lists_by_when_it_was_made(bench: Bench) -> None:
    """Mentions and ticket assignments start runs through `RunRepository.start`; their
    ids are UUIDv7 like every other, so lists stay newest first and pages exact."""
    first = await answered(bench)
    alice = bench.people.users["alice"]
    trigger = await bench.session.scalar(
        select(Message.id).where(Message.conversation_id == bench.dm["id"]).limit(1)
    )
    started = await RunRepository(bench.session, bench.agent.org_id).start(
        bench.agent.id, alice.id, bench.dm["id"], message_id=trigger
    )
    assert started is not None and started.version == 7
    assert [i["id"] for i in await listed(bench.people.alice)] == [str(started), first]


async def test_an_agents_runs_for_its_responsible_person_and_agent_manage(
    bench: Bench,
) -> None:
    run_id = await answered(bench)
    path = f"/api/agents/{bench.agent.id}/runs"
    admin_items = await listed(bench.people.admin, path)
    assert [i["id"] for i in admin_items] == [run_id]
    assert admin_items[0]["asker_name"] == "Alice"
    for who in ("bob", "carol", "gast"):
        r = await getattr(bench.people, who).get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found"
    bench.agent.responsible_user_id = bench.people.users["bob"].id
    await bench.session.flush()
    assert [i["id"] for i in await listed(bench.people.bob, path)] == [run_id]
    assert [i["id"] for i in await listed(bench.people.bob, path, state="queued")] == []
    unknown = await bench.people.admin.get("/api/agents/0190f0f0-0000-7000-8000-000000000000/runs")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "agent.not_found"


async def test_a_responsible_person_without_ai_sees_no_runs(bench: Bench) -> None:
    run_id = await answered(bench)
    bench.agent.responsible_user_id = bench.people.users["bob"].id
    await bench.session.flush()
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id('bob')}",
        json={"no_ai": True, "version": None},
    )
    assert r.status_code == 200, r.text
    assert (await bench.people.bob.get(f"/api/agents/{bench.agent.id}/runs")).status_code == 404
    assert (await bench.people.bob.get(f"{RUNS}/{run_id}")).status_code == 404


async def test_a_list_costs_the_same_statements_whatever_its_length(
    bench: Bench, session: AsyncSession
) -> None:
    await answered(bench)
    agent_runs = f"/api/agents/{bench.agent.id}/runs"
    await listed(bench.people.alice)  # warm: the first request loads more
    with counting(session) as few:
        assert len(await listed(bench.people.alice)) == 1
    with counting(session) as few_agent:
        await listed(bench.people.admin, agent_runs)
    for _ in range(5):
        await extra_run(bench)
    await extra_run(bench, state=RunState.QUEUED, reason=None)
    with counting(session) as many:
        assert len(await listed(bench.people.alice)) == 7
    with counting(session) as many_agent:
        await listed(bench.people.admin, agent_runs)
    assert len(many) == len(few)
    assert len(many_agent) == len(few_agent)
