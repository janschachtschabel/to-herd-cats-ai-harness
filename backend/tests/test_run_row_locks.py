"""A run's row under real concurrency (committed transactions on separate
connections; module review M6 2, finding 4 and the checks of findings 3 and 14).

- Taking a ticket from an agent locks ticket, then run (`FOR NO KEY UPDATE`, waiting
  at most `REASSIGN_LOCK_TIMEOUT_SECONDS`); a step of that agent's run locks run, then
  ticket. Whoever loses comes out well: the request with 409 `conflict.retry` and
  `Retry-After`, the step with a retryable error; never a 500, never a hang.
- A step that does not touch the ticket: the request waits for it only that long.
- The deadline's asyncio cut while a step waits for its row leaves nothing open.
"""

import asyncio
import time
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import Claimed, RunSteps, claim
from app.modules.agents.models import REASSIGN_LOCK_TIMEOUT_SECONDS, Agent, Run, RunCancelRequest
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.agents.step_host import RunHost, units_of
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User
from app.runtime.loop import Halt, ToolCall
from tests.factories import login
from tests.factories_agents import LEASE, assign_default, make_connection
from tests.factories_tickets import new_ticket
from tests.real_db import MakeRealClient, RealDb
from tests.support import probe_tools
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of


async def _ticket_run(
    real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub
) -> tuple[AsyncClient, dict[str, Any], Claimed]:
    """A ticket assigned to an agent and its run, claimed."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    connection = await make_connection(owner, stub, max_concurrency=4)
    await assign_default(owner, connection)
    space = (await owner.post("/api/spaces", json={"name": "Team", "kind": "team"})).json()
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
        agent: Agent = await AgentService(session).create(await actor_of(session, boss), body)
        await SpaceRepository(session).set_member(
            uuid.UUID(space["id"]), Principal.agent(agent.id), SpaceRole.EDITOR
        )
        await session.commit()
    ticket = await new_ticket(owner, space["id"], "Aufgabe")
    r = await owner.patch(
        f"/api/tickets/{ticket['number']}",
        json={"version": ticket["version"], "assignee": {"type": "agent", "id": str(agent.id)}},
    )
    assert r.status_code == 200, r.text
    async with units_of(real_db.database.session_factory)() as session:
        claimed = await claim(session, LEASE)
    assert claimed is not None and claimed.work_item_id is not None
    return owner, r.json(), claimed


async def _waiting_for_a_lock(real_db: RealDb, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    query = text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND wait_event_type = 'Lock'"
    )
    while True:
        async with real_db.database.session_factory() as session:
            if await session.scalar(query):
                return
        assert time.monotonic() < deadline, "nobody waits for a lock"
        await asyncio.sleep(0.05)


def _unassign(owner: AsyncClient, ticket: dict[str, Any]) -> Any:
    return owner.patch(
        f"/api/tickets/{ticket['number']}", json={"version": ticket["version"], "assignee": None}
    )


async def test_taking_a_ticket_against_a_step_that_changes_it_ends_well(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    """The deadlock is real. Whoever loses it must come out well: the request with
    409 `conflict.retry`, or the step with a retryable error; never a 500, never a
    hang, and afterwards the run can still be asked to stop."""
    owner, ticket, claimed = await _ticket_run(real_db, make_real_client, openai_stub)
    step_error: BaseException | None = None
    async with real_db.database.session_factory() as step:
        await step.begin()
        assert await RunSteps(step, claimed).owned() is not None  # run, as every step
        request = asyncio.create_task(_unassign(owner, ticket))  # ticket, then run
        await _waiting_for_a_lock(real_db)
        started = time.monotonic()
        try:  # run → ticket, as set_ticket_status or assign_ticket of the run do
            await step.execute(
                text("UPDATE work_item SET version = version WHERE id = :id"),
                {"id": claimed.work_item_id},
            )
            await step.commit()
        except Exception as exc:
            step_error = exc
            await step.rollback()
        response = await asyncio.wait_for(request, timeout=10)
    took = time.monotonic() - started
    from app.core.db_errors import is_retryable

    print(
        f"LOCKS status={response.status_code} body={response.text[:120]!r} "
        f"step_error={type(step_error).__name__ if step_error else None} took={took:.2f}s"
    )
    assert took < 5
    if step_error is not None:
        assert is_retryable(step_error)
        assert response.status_code == 200, response.text
    else:
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "conflict.retry"
        assert response.headers["Retry-After"] == "1"
        again = await _unassign(owner, ticket)  # the client's retry goes through
        assert again.status_code == 200, again.text
    async with real_db.database.session_factory() as session:
        asked = list(await session.scalars(select(RunCancelRequest.run_id)))
    assert asked == [claimed.id]


async def test_taking_a_ticket_waits_for_a_running_step_only_briefly(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    """A person's request does not hang on an agent's step that does not touch the
    ticket at all (a step may take 20 s and more): it answers 409 `conflict.retry`
    within the bound, and sent again once the step is done it goes through."""
    owner, ticket, claimed = await _ticket_run(real_db, make_real_client, openai_stub)
    async with real_db.database.session_factory() as step, step.begin():
        assert await RunSteps(step, claimed).owned() is not None
        started = time.monotonic()
        request = asyncio.create_task(_unassign(owner, ticket))
        done, _ = await asyncio.wait({request}, timeout=REASSIGN_LOCK_TIMEOUT_SECONDS + 2.0)
        took = time.monotonic() - started
    assert done, "PATCH /api/tickets/{n} waited for the run's step to end"
    response = request.result()
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "conflict.retry"
    assert response.headers["Retry-After"] == "1"
    assert took >= REASSIGN_LOCK_TIMEOUT_SECONDS * 0.9
    again = await _unassign(owner, ticket)
    assert again.status_code == 200, again.text
    async with real_db.database.session_factory() as session:
        asked = list(await session.scalars(select(RunCancelRequest.run_id)))
    assert asked == [claimed.id]


async def test_the_deadline_cuts_a_step_that_waits_for_its_row(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The asyncio cut (deadline + 1 s) of a step that waits in the database with no
    statement bound yet (its first statement locks the run's row): the run ends
    `deadline`, and no transaction of the worker stays open or waiting."""
    probe_tools.installed(monkeypatch)
    owner, ticket, claimed = await _ticket_run(real_db, make_real_client, openai_stub)
    factory = real_db.database.session_factory
    unit = units_of(factory)
    prepared = await Executor(unit)._prepare(claimed)
    assert isinstance(prepared, tuple)
    run = prepared[0]
    host = RunHost(unit, time.monotonic, run)
    host.tools["probe_write"] = probe_tools.PROBES[0]
    run.deadline = time.monotonic() + 0.5
    async with factory() as holder, holder.begin():
        await holder.execute(select(Run.id).where(Run.id == claimed.id).with_for_update())
        started = time.monotonic()
        with pytest.raises(Halt) as halt:
            await host.call_tool(
                1, ToolCall("c1", "probe_write", {"label": "x"}), probe_tools.ProbeArgs(label="x")
            )
        took = time.monotonic() - started
        assert halt.value.reason == "deadline"
        assert took < 4, took
        await asyncio.sleep(0.3)
        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT state, wait_event_type, left(query, 60) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                        "AND (wait_event_type = 'Lock' OR state LIKE 'idle in transaction%')"
                    )
                )
            ).all()
        print("CUT took", round(took, 2), "left behind:", rows)
        # the holder itself is idle in transaction; nothing else may be
        assert [r for r in rows if r[1] == "Lock"] == []
        assert len(rows) == 1
    async with factory() as session:
        assert await probe_tools.effects(session, claimed.id) == []
