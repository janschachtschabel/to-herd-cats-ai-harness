"""Approvals that race, over separate connections with real commits (tests/real_db.py):
two decisions at once, a decision against the expiry, against a cancel request, and a
page edited while the released call runs. The run's row lock decides between them
(the same order everywhere: the run, then the approval), and the fingerprint between
a release and an edit."""

import asyncio
import uuid
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select, update

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
from app.core.models_base import utcnow
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents import control
from app.modules.agents.approvals.models import Approval, ApprovalState
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import claim
from app.modules.agents.models import Agent, Run, RunState, StopReason
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.agents.step_host import units_of
from app.modules.proposals.models import PageProposal
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User
from tests.factories import login
from tests.factories_agents import LEASE, assign_default, make_connection
from tests.factories_tools import call
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of


class Scene:
    def __init__(self, real_db: RealDb, owner: AsyncClient, stub: OpenAIStub) -> None:
        self.db = real_db
        self.owner = owner
        self.stub = stub
        self.agent: Agent
        self.dm: str
        self.page: dict[str, Any]

    async def run_next(self) -> StopReason | None:
        unit = units_of(self.db.database.session_factory)
        async with unit() as session:
            claimed = await claim(session, LEASE)
        assert claimed is not None
        return await Executor(unit).execute(claimed)

    async def asked(self) -> tuple[uuid.UUID, dict[str, Any]]:
        """A run that called `propose_page_change` and waits for its release."""
        args = {"page_id": self.page["id"], "content_md": "NEU\n", "reason": "r"}
        self.stub.state.replies.extend(
            [call("propose_page_change", **args), {"content": "Erledigt."}]
        )
        r = await self.owner.post(
            f"/api/conversations/{self.dm}/messages", json={"body_md": "Bitte"}
        )
        assert r.status_code == 201, r.text
        assert await self.run_next() is None
        pending = await self.owner.get("/api/approvals", params={"state": "pending"})
        approval = pending.json()["items"][0]
        return uuid.UUID(r.json()["agent_run"]["id"]), approval

    def decide(self, approval: dict[str, Any], client: AsyncClient | None = None) -> Any:
        body = {"decision": "approve", "version": approval["version"]}
        return (client or self.owner).post(f"/api/approvals/{approval['id']}/decide", json=body)

    async def run(self, run_id: uuid.UUID) -> Run:
        async with self.db.database.session_factory() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            return run

    async def approval(self, approval_id: str) -> Approval:
        async with self.db.database.session_factory() as session:
            row = await session.get(Approval, uuid.UUID(approval_id))
            assert row is not None
            return row


async def _scene(real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub) -> Scene:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    connection = await make_connection(owner, stub, max_concurrency=4)
    await assign_default(owner, connection)
    space = (await owner.post("/api/spaces", json={"name": "Race", "kind": "team"})).json()
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
        await SpaceRepository(session).set_member(
            uuid.UUID(space["id"]), Principal.agent(agent.id), SpaceRole.EDITOR
        )
        await session.commit()
    scene = Scene(real_db, owner, stub)
    scene.agent = agent
    put = {"tools": [{"tool": "propose_page_change", "policy": "confirm"}], "version": 1}
    r = await owner.put(f"/api/agents/{agent.id}/tools", json=put)
    assert r.status_code == 200, r.text
    made = await owner.post(
        f"/api/spaces/{space['id']}/pages", json={"title": "Seite", "content_md": "alt\n"}
    )
    page = made.json()
    published = await owner.post(
        f"/api/pages/{page['id']}/publish", json={"version": page["version"]}
    )
    assert published.status_code == 200, published.text
    scene.page = published.json()
    scene.dm = (await owner.post("/api/dms", json={"agent_id": str(agent.id)})).json()["id"]
    return scene


async def _proposals(real_db: RealDb) -> int:
    async with real_db.database.session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(PageProposal)) or 0)


async def test_two_decisions_at_once_one_wins(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    scene = await _scene(real_db, make_real_client, openai_stub)
    run_id, approval = await scene.asked()
    other = await make_real_client()
    await login(other, real_db.owner_email)
    answers = await asyncio.gather(scene.decide(approval), scene.decide(approval, other))
    assert sorted(a.status_code for a in answers) == [200, 409]
    loser = next(a for a in answers if a.status_code == 409)
    assert loser.json()["error"]["code"] == "approval.decided"
    assert (await scene.run(run_id)).state == RunState.QUEUED
    assert await scene.run_next() == StopReason.COMPLETED
    assert await _proposals(real_db) == 1


async def test_a_decision_against_the_expiry(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    scene = await _scene(real_db, make_real_client, openai_stub)
    run_id, approval = await scene.asked()
    soon = utcnow() + timedelta(milliseconds=20)
    async with real_db.database.session_factory() as session:
        await session.execute(update(Run).where(Run.id == run_id).values(wait_until=soon))
        await session.execute(
            update(Approval).where(Approval.id == uuid.UUID(approval["id"])).values(expires_at=soon)
        )
        await session.commit()
    await asyncio.sleep(0.02)

    async def sweep() -> int:
        async with real_db.database.session_factory() as session, session.begin():
            return await control.sweep_waiting(session)

    decided, _ = await asyncio.gather(scene.decide(approval), sweep())
    await sweep()  # a sweep that passed over the run while the decision held it
    run, row = await scene.run(run_id), await scene.approval(approval["id"])
    if decided.status_code == 200:  # decided in time: the run goes on, nothing ends it
        assert run.state == RunState.QUEUED and row.state == ApprovalState.APPROVED
    else:
        assert decided.json()["error"]["code"] == "approval.expired"
        assert run.stop_reason == StopReason.APPROVAL_EXPIRED
        assert row.state == ApprovalState.EXPIRED
    assert await _proposals(real_db) == 0


async def test_a_decision_against_a_cancel_request(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    scene = await _scene(real_db, make_real_client, openai_stub)
    run_id, approval = await scene.asked()

    async def cancel() -> bool:
        async with real_db.database.session_factory() as session, session.begin():
            boss = await session.scalar(select(User).where(User.email == real_db.owner_email))
            assert boss is not None
            return await control.request_cancel(session, real_db.org_id, run_id, boss.id)  # type: ignore[arg-type]

    decided, cancelled = await asyncio.gather(scene.decide(approval), cancel())
    assert cancelled
    if decided.status_code == 200:  # the release came first; the run stops when taken up
        assert await scene.run_next() == StopReason.CANCELLED
    else:
        assert decided.json()["error"]["code"] == "approval.run_ended"
        async with real_db.database.session_factory() as session, session.begin():
            assert await control.sweep_waiting(session) == 1
        assert (await scene.run(run_id)).stop_reason == StopReason.CANCELLED
    assert await _proposals(real_db) == 0


async def test_a_page_edited_while_the_released_call_runs(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    scene = await _scene(real_db, make_real_client, openai_stub)
    _, approval = await scene.asked()
    assert (await scene.decide(approval)).status_code == 200
    edit = scene.owner.patch(
        f"/api/pages/{scene.page['id']}",
        json={"content_md": "von Hand\n", "version": scene.page["version"]},
    )
    stopped, edited = await asyncio.gather(scene.run_next(), edit)
    assert stopped == StopReason.COMPLETED and edited.status_code == 200
    stale = "approval_stale" in openai_stub.state.texts()
    # Either the call ran before the edit, or it found the page changed and ran nothing.
    assert (await _proposals(real_db)) == (0 if stale else 1)
