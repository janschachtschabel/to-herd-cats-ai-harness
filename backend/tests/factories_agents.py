"""Agent fixtures: `bench` is an organisation with AI (a `local` connection to the
OpenAI stub, the default assignment on it, so every member has `ai.use`), an active
agent `Ava` (responsible: the admin) and Alice's DM with it; plus helpers to say
something there, to run the next run in the test's transaction and to read the DM.

The connection's data location is `external` unless a test changes it, so a
`restricted` space keeps its content from it.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.executor import Executor, ModelMaker
from app.modules.agents.executor_repository import claim
from app.modules.agents.models import Agent
from app.modules.agents.run_models import Run, StopReason
from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.ai.models import AiConnection
from app.modules.spaces.models import Space
from app.modules.spaces.repository import SpaceRepository
from app.runtime import models
from tests.factories_dms import People
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of

CONNECTIONS = "/api/ai/connections"
ASSIGNMENTS = "/api/ai/assignments"
LEASE = 30.0


@dataclass
class Bench:
    session: AsyncSession
    people: People
    stub: OpenAIStub
    connection: AiConnection
    agent: Agent
    dm: dict[str, Any]
    make_model: ModelMaker = models.make_model

    @property
    def dm_id(self) -> str:
        return str(self.dm["id"])

    def unit(self) -> Any:
        """The executor's unit of work, in the test's transaction (a savepoint)."""
        session = self.session

        @asynccontextmanager
        async def _unit() -> AsyncIterator[AsyncSession]:
            nested = await session.begin_nested()
            try:
                yield session
            except BaseException:
                if nested.is_active:
                    await nested.rollback()
                raise
            if nested.is_active:
                await nested.commit()

        return _unit

    def executor(self, **kwargs: Any) -> Executor:
        return Executor(self.unit(), make_model=kwargs.pop("make_model", self.make_model), **kwargs)

    async def say(self, text: str, who: str = "alice", dm: str | None = None) -> dict[str, Any]:
        client: AsyncClient = getattr(self.people, who)
        r = await client.post(
            f"/api/conversations/{dm or self.dm_id}/messages", json={"body_md": text}
        )
        assert r.status_code == 201, r.text
        body: dict[str, Any] = r.json()
        return body

    async def run_next(self, executor: Executor | None = None) -> StopReason | None:
        """Claim the next run and work it to its end (asserts there was one)."""
        async with self.unit()() as session:
            claimed = await claim(session, LEASE)
        assert claimed is not None, "no run to claim"
        return await (executor or self.executor()).execute(claimed)

    async def messages(self, who: str = "alice") -> list[dict[str, Any]]:
        client: AsyncClient = getattr(self.people, who)
        r = await client.get(f"/api/conversations/{self.dm_id}/messages?limit=100")
        assert r.status_code == 200, r.text
        items: list[dict[str, Any]] = r.json()["items"]
        return sorted(items, key=lambda m: m["id"])

    async def run_of(self, run_id: object) -> Run:
        run = await self.session.scalar(
            select(Run).where(Run.id == run_id).execution_options(populate_existing=True)
        )
        assert run is not None
        return run

    async def join(self, space: Space, role: SpaceRole = SpaceRole.VIEWER) -> None:
        """The agent becomes a member of the space."""
        repo = SpaceRepository(self.session)
        await repo.set_member(space.id, Principal.agent(self.agent.id), role)

    async def locate(self, location: str) -> None:
        self.connection.data_location = location  # type: ignore[assignment]
        await self.session.flush()


async def make_connection(admin: AsyncClient, stub: OpenAIStub, **fields: Any) -> dict[str, Any]:
    body = {
        "name": "Stub",
        "kind": "local",
        "base_url": stub.base_url,
        "models": ["m1"],
        "data_location": "external",
        "requests_per_minute": 600,
        **fields,
    }
    r = await admin.post(CONNECTIONS, json=body)
    assert r.status_code == 201, r.text
    connection: dict[str, Any] = r.json()
    return connection


async def assign_default(admin: AsyncClient, connection: dict[str, Any] | None) -> None:
    version = (await admin.get(ASSIGNMENTS)).json()["version"]
    target = {"connection_id": connection["id"], "model": "m1"} if connection else None
    r = await admin.put(f"{ASSIGNMENTS}/default", json={"target": target, "version": version})
    assert r.status_code == 200, r.text


async def make_agent(
    session: AsyncSession, people: People, connection_id: object, **fields: Any
) -> Agent:
    admin = await actor_of(session, people.users["admin"])
    body = {
        "name": "Ava",
        "intro": "Answers questions from the wiki.",
        "instructions": "Be brief.",
        "connection_id": connection_id,
        "model": "m1",
        "responsible_user_id": people.users["admin"].id,
        "status": "active",
        **fields,
    }
    return await AgentService(session).create(admin, AgentCreate.model_validate(body))


async def open_agent_dm(client: AsyncClient, agent: Agent) -> dict[str, Any]:
    r = await client.post("/api/dms", json={"agent_id": str(agent.id)})
    assert r.status_code in (200, 201), r.text
    dm: dict[str, Any] = r.json()
    return dm


@pytest.fixture
async def bench(
    session: AsyncSession,
    people: People,
    openai_stub: OpenAIStub,
) -> Bench:
    made = await make_connection(people.admin, openai_stub)
    await assign_default(people.admin, made)
    connection = await session.get(AiConnection, made["id"])
    assert connection is not None
    agent = await make_agent(session, people, connection.id)
    dm = await open_agent_dm(people.alice, agent)
    return Bench(session, people, openai_stub, connection, agent, dm)
