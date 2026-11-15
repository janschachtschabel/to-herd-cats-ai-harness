"""The worker's run loop with real commits (`tests/real_db.py`): a run waits for its
provider with no database connection held (a pool of one connection stays usable),
two workers answer each run once, and the gauges count waiting runs."""

import asyncio
import time
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select, text

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
import app.worker.runs as worker_runs
from app.core.config import get_settings
from app.core.db import Database
from app.modules.agents.models import Agent
from app.modules.agents.run_models import Run, RunState
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.messaging.models import Message, MessageKind
from app.modules.users.models import User
from app.worker.runs import RunLoop, run_metrics
from tests.factories import login
from tests.factories_agents import assign_default, make_connection
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of

FAST_ENOUGH = 1.0


@pytest.fixture
async def one_connection(real_db: RealDb) -> AsyncIterator[Database]:
    database = Database(
        get_settings().test_database_url, pool_size=1, max_overflow=0, pool_timeout=10
    )
    try:
        yield database
    finally:
        await database.dispose()


async def _setup(
    real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub
) -> tuple[Agent, list[str]]:
    """An agent and the DM of the owner and of the member with it."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    connection = await make_connection(owner, stub, max_concurrency=4)
    await assign_default(owner, connection)
    async with real_db.database.session_factory() as session:
        people = {u.email: u for u in (await session.scalars(select(User))).all()}
        boss = people[real_db.owner_email]
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
    dms = []
    for email in (real_db.owner_email, real_db.member_email):
        client = await make_real_client()
        await login(client, email)
        dm = (await client.post("/api/dms", json={"agent_id": str(agent.id)})).json()
        r = await client.post(f"/api/conversations/{dm['id']}/messages", json={"body_md": "Hi"})
        assert r.status_code == 201 and r.json()["agent_run"]["id"], r.text
        dms.append(dm["id"])
    return agent, dms


async def _until(predicate: object, seconds: float = 10) -> None:
    deadline = time.monotonic() + seconds
    while not await predicate():  # type: ignore[operator]
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.05)


async def test_a_run_holds_no_connection_while_the_provider_works(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    one_connection: Database,
) -> None:
    await _setup(real_db, make_real_client, openai_stub)
    openai_stub.state.delay = 1.5
    stop = asyncio.Event()
    loop = RunLoop(one_connection, concurrency=2, lease=30)
    serving = asyncio.create_task(loop.serve(stop))
    try:

        async def calling() -> bool:
            return len(openai_stub.state.log) >= 2  # both runs wait for the provider

        await _until(calling)
        started = time.perf_counter()
        async with one_connection.session_factory() as session:
            assert await session.scalar(text("SELECT 1")) == 1
        assert time.perf_counter() - started < FAST_ENOUGH

        async def answered() -> bool:
            async with real_db.database.session_factory() as session:
                count = await session.scalar(
                    select(func.count()).where(Message.kind == MessageKind.AGENT)
                )
                return count == 2

        await _until(answered)
    finally:
        stop.set()
        await serving


async def test_two_workers_answer_each_run_once(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    _, dms = await _setup(real_db, make_real_client, openai_stub)
    stop = asyncio.Event()
    loops = [RunLoop(real_db.database, concurrency=4, lease=30) for _ in range(2)]
    serving = [asyncio.create_task(loop.serve(stop)) for loop in loops]
    try:

        async def done() -> bool:
            async with real_db.database.session_factory() as session:
                states = (await session.scalars(select(Run.state))).all()
                return len(states) == 2 and all(s == RunState.DONE for s in states)

        await _until(done)
    finally:
        stop.set()
        await asyncio.gather(*serving)
    async with real_db.database.session_factory() as session:
        answers = (
            await session.execute(
                select(Message.conversation_id, Message.client_id).where(
                    Message.kind == MessageKind.AGENT
                )
            )
        ).all()
        runs = (await session.execute(select(Run.id, Run.attempt))).all()
    assert sorted(str(c) for c, _ in answers) == sorted(dms)
    assert all(attempt == 1 for _, attempt in runs)
    assert len(openai_stub.state.log) == 2


async def test_the_gauges_count_waiting_runs(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    await _setup(real_db, make_real_client, openai_stub)
    loop = RunLoop(real_db.database, concurrency=1, lease=30)
    await loop.update_metrics()
    metrics = run_metrics()
    assert metrics.queued._value.get() == 2  # noqa: SLF001
    assert metrics.oldest_queued._value.get() >= 0  # noqa: SLF001
    assert metrics.stuck._value.get() == 0  # noqa: SLF001


async def test_a_failing_sweep_does_not_stop_the_claims(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ending the due waiting runs and claiming queued ones fail apart: while the sweep
    fails every time, queued runs are still answered."""

    async def broken(session: object) -> int:
        raise RuntimeError("a waiting run whose end cannot be written")

    monkeypatch.setattr(worker_runs, "sweep_waiting", broken)
    await _setup(real_db, make_real_client, openai_stub)
    loop = RunLoop(real_db.database, concurrency=2, lease=30)
    stop = asyncio.Event()
    task = asyncio.create_task(loop.serve(stop))

    async def answered() -> bool:
        async with real_db.database.session_factory() as session:
            left = select(func.count()).select_from(Run).where(Run.state != RunState.DONE)
            return await session.scalar(left) == 0

    try:
        await _until(answered)
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=10)
    assert any(r.message == "runs.sweep_failed" for r in caplog.records)
    assert not any(r.message == "runs.claim_failed" for r in caplog.records)
