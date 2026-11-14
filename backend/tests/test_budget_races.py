"""Budgets under real commits and concurrent requests (`tests/real_db.py`): one
subject's budget created twice at once, one conflicts; two changes of one version, one
conflicts. Two runs of one agent at its limit, on their own connections: a limit
reached stops both before any call; calls in flight at once each pass the limit by
that one call, and neither run makes another."""

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import claim
from app.modules.agents.models import StopReason
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.agents.step_host import RunHost, units_of
from app.modules.ai.usage import record_usage
from app.modules.users.models import User
from app.runtime.loop import Reply
from tests.factories import login
from tests.factories_agents import LEASE, assign_default, make_connection
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of

BUDGETS = "/api/ai/budgets"
ROUNDS = 4


async def _owners(real_db: RealDb, make_real_client: MakeRealClient) -> list[AsyncClient]:
    clients = [await make_real_client() for _ in range(2)]
    for client in clients:
        await login(client, real_db.owner_email)
    return clients


async def test_one_budget_per_subject_and_version(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    first, second = await _owners(real_db, make_real_client)
    me = (await first.get("/api/auth/me")).json()["user"]["id"]
    for round_ in range(ROUNDS):
        path = f"{BUDGETS}/organisation" if round_ % 2 else f"{BUDGETS}/users/{me}"
        created = await asyncio.gather(
            *(c.put(path, json={"tokens_per_day": 10, "version": None}) for c in (first, second))
        )
        assert sorted(r.status_code for r in created) == [200, 409], [r.text for r in created]
        made = next(r.json() for r in created if r.status_code == 200)
        changed = await asyncio.gather(
            *(
                c.put(path, json={"tokens_per_day": n, "version": made["version"]})
                for n, c in ((20, first), (30, second))
            )
        )
        assert sorted(r.status_code for r in changed) == [200, 409], [r.text for r in changed]
        version = next(r.json()["version"] for r in changed if r.status_code == 200)
        r = await first.delete(f"{BUDGETS}/{made['id']}", params={"version": version})
        assert r.status_code == 204, r.text


async def _two_asking(
    real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub
) -> tuple[Any, list[AsyncClient], list[str]]:
    """Owner and member, each with a DM to the agent Ava (budget: 1 token a day)."""
    owner, member = await make_real_client(), await make_real_client()
    await login(owner, real_db.owner_email)
    await login(member, real_db.member_email)
    connection = await make_connection(owner, stub)
    await assign_default(owner, connection)
    async with real_db.database.session_factory() as session:
        boss = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert boss is not None
        body = {
            "name": "Ava",
            "connection_id": connection["id"],
            "model": "m1",
            "responsible_user_id": boss.id,
            "status": "active",
        }
        agent = await AgentService(session).create(
            await actor_of(session, boss), AgentCreate.model_validate(body)
        )
        await session.commit()
    r = await owner.put(f"{BUDGETS}/agents/{agent.id}", json={"tokens_per_day": 1, "version": None})
    assert r.status_code == 200, r.text
    dms = [
        (await c.post("/api/dms", json={"agent_id": str(agent.id)})).json()["id"]
        for c in (owner, member)
    ]
    return agent, [owner, member], dms


async def _run_both(real_db: RealDb, clients: list[AsyncClient], dms: list[str]) -> list[Any]:
    for client, dm in zip(clients, dms, strict=True):
        r = await client.post(f"/api/conversations/{dm}/messages", json={"body_md": "Such"})
        assert r.status_code == 201 and r.json()["agent_run"]["id"], r.text
    claimed = []
    for _ in clients:
        async with real_db.database.session_factory() as session, session.begin():
            claimed.append(await claim(session, LEASE))
    executor = Executor(units_of(real_db.database.session_factory))
    return list(await asyncio.gather(*(executor.execute(c) for c in claimed)))


async def test_a_reached_limit_stops_runs_at_once(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    agent, clients, dms = await _two_asking(real_db, make_real_client, openai_stub)
    async with real_db.database.session_factory() as session, session.begin():
        await record_usage(
            session,
            org_id=agent.org_id,
            connection_id=agent.connection_id,
            model="m1",
            tokens_in=1,
            tokens_out=0,
            duration_ms=1,
            agent_id=agent.id,
        )
    assert await _run_both(real_db, clients, dms) == [StopReason.BUDGET] * 2
    assert openai_stub.state.log == []


async def test_calls_in_flight_pass_the_limit_once_each(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, clients, dms = await _two_asking(real_db, make_real_client, openai_stub)
    search = {"tool_calls": [{"name": "search", "arguments": {"query": "x"}}]}
    openai_stub.state.replies.extend([search, search, {"content": "a"}, {"content": "b"}])
    both_answered = asyncio.Barrier(2)
    original = RunHost.after_model_call

    async def after_both_calls(self: RunHost, step: int, reply: Reply) -> None:
        await both_answered.wait()  # both calls went out before either is booked
        await original(self, step, reply)

    monkeypatch.setattr(RunHost, "after_model_call", after_both_calls)
    assert await _run_both(real_db, clients, dms) == [StopReason.BUDGET] * 2
    assert len(openai_stub.state.log) == 2  # one call each, the limit passed by those
