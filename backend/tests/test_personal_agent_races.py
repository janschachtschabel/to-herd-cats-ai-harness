"""Personal agents created at once, with real commits (`tests/real_db.py`): they are
counted under a lock per person, so the limit holds (plan M6 decision 13)."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.modules.agents.models import Agent
from tests.factories import login
from tests.factories_agents import assign_default, make_connection
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub


async def test_creating_personal_agents_at_once_keeps_the_limit(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    await assign_default(owner, await make_connection(owner, openai_stub))
    members = [await make_real_client() for _ in range(3)]
    for client in members:
        await login(client, real_db.member_email)
    monkeypatch.setattr(get_settings(), "ai_personal_agents_max", 1)

    async def create(client: AsyncClient, name: str) -> int:
        r = await client.post("/api/agents", json={"name": name, "personal": True})
        return r.status_code

    first = await asyncio.gather(*(create(c, f"A{i}") for i, c in enumerate(members[:2])))
    assert sorted(first) == [201, 409]
    monkeypatch.setattr(get_settings(), "ai_personal_agents_max", 3)
    second = await asyncio.gather(*(create(c, f"B{i}") for i, c in enumerate(members)))
    assert sorted(second) == [201, 201, 409]
    async with real_db.database.session_factory() as session:
        owned = await session.scalar(
            select(func.count()).select_from(Agent).where(Agent.owner_user_id.is_not(None))
        )
    assert owned == 3
