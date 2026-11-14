"""Cancelling against the run's own end, with real commits (`tests/real_db.py`): the
cancel request and the run's finish both lock the run's row, so either the finish
sees the request (`cancelled`, no answer) or the request finds the run done (409
`run.finished`, the answer stands); never both. The same against a waiting run being
resumed: the run ends `cancelled` either way, once, and no worker takes it up."""

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

import app.modules.agents.executor as executor_module
import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
from app.modules.agents import control
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import claim
from app.modules.agents.models import Run, RunState, StopReason
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.agents.step_host import units_of
from app.modules.messaging.models import Message, MessageKind
from app.modules.users.models import User
from tests.factories import login
from tests.factories_agents import LEASE, assign_default, make_connection
from tests.real_db import MakeRealClient, RealDb
from tests.support import probe_tools
from tests.support.openai_stub import OpenAIStub
from tests.support.probe_tools import ANSWERED
from tests.test_access import actor_of

BLOCKED = 0.3  # long enough to see that the cancel waits on the row


@pytest.fixture(autouse=True)
def _probes(monkeypatch: pytest.MonkeyPatch) -> None:
    probe_tools.installed(monkeypatch)
    ANSWERED.clear()


async def _dm(real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub) -> Any:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    connection = await make_connection(owner, stub)
    await assign_default(owner, connection)
    async with real_db.database.session_factory() as session:
        boss = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert boss is not None
        body = AgentCreate.model_validate(
            {
                "name": "Ava",
                "connection_id": connection["id"],
                "model": "m1",
                "responsible_user_id": boss.id,
                "status": "active",
            }
        )
        agent = await AgentService(session).create(await actor_of(session, boss), body)
        await session.commit()
    dm = (await owner.post("/api/dms", json={"agent_id": str(agent.id)})).json()
    return owner, dm["id"], agent.org_id


async def _ask(client: AsyncClient, dm_id: str) -> uuid.UUID:
    r = await client.post(f"/api/conversations/{dm_id}/messages", json={"body_md": "Hi"})
    assert r.status_code == 201 and r.json()["agent_run"]["id"], r.text
    return uuid.UUID(r.json()["agent_run"]["id"])


async def _state(real_db: RealDb, run_id: uuid.UUID) -> tuple[str, str | None, int]:
    async with real_db.database.session_factory() as session:
        run = await session.get_one(Run, run_id)
        answers = await session.scalar(
            select(func.count()).where(
                Message.kind == MessageKind.AGENT, Message.client_id == run_id
            )
        )
        return run.state, run.stop_reason, int(answers or 0)


async def _claimed(real_db: RealDb) -> Any:
    async with real_db.database.session_factory() as session, session.begin():
        return await claim(session, LEASE)


async def test_a_cancel_before_the_finish_wins(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dm_id, _ = await _dm(real_db, make_real_client, openai_stub)
    run_id = await _ask(owner, dm_id)
    claimed = await _claimed(real_db)
    executor = Executor(units_of(real_db.database.session_factory))
    asked = asyncio.Event()
    original = Executor._finish

    async def finish_after_the_request(self: Executor, *args: Any) -> StopReason:
        await asked.wait()
        return await original(self, *args)

    monkeypatch.setattr(Executor, "_finish", finish_after_the_request)
    working = asyncio.create_task(executor.execute(claimed))
    try:
        r = await owner.post(f"/api/runs/{run_id}/cancel")
        assert r.status_code == 200 and r.json()["state"] == "running", r.text
    finally:
        asked.set()
    assert await working == StopReason.CANCELLED
    assert await _state(real_db, run_id) == ("done", "cancelled", 0)


async def test_a_cancel_during_the_finish_waits_and_finds_it_done(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dm_id, _ = await _dm(real_db, make_real_client, openai_stub)
    run_id = await _ask(owner, dm_id)
    claimed = await _claimed(real_db)
    executor = Executor(units_of(real_db.database.session_factory))
    closed, go_on = asyncio.Event(), asyncio.Event()
    original = executor_module.close

    async def hold_the_finish(*args: Any, **kwargs: Any) -> StopReason:
        reason = await original(*args, **kwargs)  # written, the row locked, not committed
        closed.set()
        await go_on.wait()
        return reason

    monkeypatch.setattr(executor_module, "close", hold_the_finish)
    working = asyncio.create_task(executor.execute(claimed))
    try:
        await closed.wait()
        cancelling = asyncio.create_task(owner.post(f"/api/runs/{run_id}/cancel"))
        await asyncio.sleep(BLOCKED)
        assert not cancelling.done()  # waits on the run's row
    finally:
        go_on.set()
    assert await working == StopReason.COMPLETED
    r = await cancelling
    assert r.status_code == 409 and r.json()["error"]["code"] == "run.finished"
    assert await _state(real_db, run_id) == ("done", "completed", 1)


async def _waiting(real_db: RealDb, stub: OpenAIStub, owner: AsyncClient, dm_id: str) -> uuid.UUID:
    stub.state.replies.append({"tool_calls": [{"name": "probe_wait", "arguments": {"label": "?"}}]})
    run_id = await _ask(owner, dm_id)
    executor = Executor(units_of(real_db.database.session_factory))
    assert await executor.execute(await _claimed(real_db)) is None
    assert (await _state(real_db, run_id))[0] == RunState.WAITING
    return run_id


async def test_a_cancel_against_a_resume_in_progress_ends_the_queued_run(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    owner, dm_id, org_id = await _dm(real_db, make_real_client, openai_stub)
    run_id = await _waiting(real_db, openai_stub, owner, dm_id)
    async with real_db.database.session_factory() as session:
        async with session.begin():
            assert await control.resume_waiting(session, org_id, run_id)  # row locked
            cancelling = asyncio.create_task(owner.post(f"/api/runs/{run_id}/cancel"))
            await asyncio.sleep(BLOCKED)
            assert not cancelling.done()
    r = await cancelling
    assert r.status_code == 200 and r.json()["stop_reason"] == "cancelled", r.text
    assert await _state(real_db, run_id) == ("done", "cancelled", 0)
    assert await _claimed(real_db) is None


async def test_a_resume_after_the_cancel_finds_nothing_to_resume(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    owner, dm_id, org_id = await _dm(real_db, make_real_client, openai_stub)
    run_id = await _waiting(real_db, openai_stub, owner, dm_id)
    r = await owner.post(f"/api/runs/{run_id}/cancel")
    assert r.status_code == 200 and r.json()["stop_reason"] == "cancelled"
    async with real_db.database.session_factory() as session, session.begin():
        assert not await control.resume_waiting(session, org_id, run_id)
    assert await _state(real_db, run_id) == ("done", "cancelled", 0)
    assert await _claimed(real_db) is None
