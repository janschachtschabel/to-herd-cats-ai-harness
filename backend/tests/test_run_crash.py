"""Plan M6 task 1 and review focus 4 (durability): a worker process is killed (SIGKILL)
before, inside and after a writing tool's step; another worker takes the run up again.
No step happens twice: the provider is called once per step, the effect is committed
once, the answer written once. Real commits, a real child process
(`tests/run_crash_child.py`), the OpenAI stub in this process."""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, text

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
from app.core.config import get_settings
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import claim
from app.modules.agents.run_models import EventKind, Run, RunEvent, StopReason
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.agents.step_host import units_of
from app.modules.messaging.models import Message, MessageKind
from app.modules.users.models import User
from tests.factories import login
from tests.factories_agents import assign_default, make_connection
from tests.real_db import MakeRealClient, RealDb
from tests.support import probe_tools
from tests.support.openai_stub import OpenAIStub
from tests.support.probe_tools import count, effects
from tests.test_access import actor_of

BACKEND = Path(__file__).resolve().parent.parent


async def _ask(real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub) -> str:
    """The owner's agent, a DM with it and a message: one queued run (committed)."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
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
    dm = (await owner.post("/api/dms", json={"agent_id": str(agent.id)})).json()
    r = await owner.post(f"/api/conversations/{dm['id']}/messages", json={"body_md": "Write"})
    assert r.status_code == 201 and r.json()["agent_run"]["id"], r.text
    return str(r.json()["agent_run"]["id"])


async def _kill_at(point: str) -> None:
    env = {**os.environ, "HERD_TEST_DATABASE_URL": get_settings().test_database_url}
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tests.run_crash_child",
        point,
        cwd=BACKEND,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert child.stdout is not None and child.stderr is not None
        line = await asyncio.wait_for(child.stdout.readline(), timeout=60)
        if line.strip() != point.encode():
            pytest.fail((await child.stderr.read()).decode()[-3000:])
    finally:
        if child.returncode is None:
            child.send_signal(signal.SIGKILL)
        await child.wait()


@pytest.mark.parametrize(
    ("point", "committed"), [("after-model", []), ("in-tool", []), ("after-tool", ["k"])]
)
async def test_a_killed_worker_does_no_step_twice(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
    point: str,
    committed: list[str],
) -> None:
    probe_tools.installed(monkeypatch)
    openai_stub.state.replies.extend(
        [
            {"tool_calls": [{"name": "probe_write", "arguments": {"label": "k"}}]},
            {"content": "Done."},
        ]
    )
    run_id = await _ask(real_db, make_real_client, openai_stub)
    await _kill_at(point)
    assert len(openai_stub.state.log) == 1  # the child's one call, for step 1
    database = real_db.database
    async with database.session_factory() as session:
        assert await effects(session) == committed
    async with database.session_factory() as session, session.begin():
        # The dead worker's lease runs out (waits for Postgres to drop its locks).
        await session.execute(text("UPDATE run SET lease_until = now() - interval '1 second'"))
    async with database.session_factory() as session, session.begin():
        claimed = await claim(session, 30)
    assert claimed is not None and str(claimed.id) == run_id and claimed.attempt == 2
    assert await Executor(units_of(database.session_factory)).execute(claimed) == (
        StopReason.COMPLETED
    )
    assert len(openai_stub.state.log) == 2  # step 2 only: step 1 came from the journal
    assert "wrote k" in json.dumps(openai_stub.state.log[1].body["messages"])  # ... with its result
    async with database.session_factory() as session:
        assert await effects(session) == ["k"]
        answers = await session.scalars(
            select(Message.body_md).where(Message.kind == MessageKind.AGENT)
        )
        assert list(answers) == ["Done."]
        assert await count(session, RunEvent, RunEvent.kind == EventKind.TOOL_CALL) == 1
        assert await count(session, RunEvent, RunEvent.kind == EventKind.MODEL_CALL) == 2
        run: Any = await session.get(Run, claimed.id)
        assert (run.state, run.attempt, run.recoveries, run.steps) == ("done", 2, 1, 2)
