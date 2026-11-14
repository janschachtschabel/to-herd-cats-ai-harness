"""Skill writes that race, over separate connections with real commits
(tests/real_db.py): the skill's row lock and `version` decide between changes (one
wins, one 409, one version written); the organisation's lock on skill names between
two skills of one name; the agent's `version` between two settings of its skills."""

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.modules.agents.schemas import AgentCreate
from app.modules.agents.service import AgentService
from app.modules.skills.models import AgentSkill, Skill, SkillVersion
from app.modules.users.models import User
from tests.factories import login
from tests.factories_agents import assign_default, make_connection
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of

ROUNDS = 4
SKILLS = "/api/skills"


async def _owner(make_real_client: MakeRealClient, real_db: RealDb) -> AsyncClient:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    return owner


async def _skill(owner: AsyncClient, name: str) -> str:
    r = await owner.post(SKILLS, json={"name": name, "description": "d", "content": "c"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _versions(real_db: RealDb, skill_id: str) -> int:
    async with real_db.database.session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(SkillVersion)
            .where(SkillVersion.skill_id == uuid.UUID(skill_id))
        )
        return int(count or 0)


async def test_two_changes_of_one_version_have_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await _owner(make_real_client, real_db)
    for n in range(ROUNDS):
        skill_id = await _skill(owner, f"race-{n}")
        responses = await asyncio.gather(
            owner.patch(f"{SKILLS}/{skill_id}", json={"content": "eins", "version": 1}),
            owner.patch(f"{SKILLS}/{skill_id}", json={"content": "zwei", "version": 1}),
            owner.post(f"{SKILLS}/{skill_id}/versions/1/restore", json={"version": 1}),
        )
        assert sorted(r.status_code for r in responses) == [200, 409, 409]
        codes = {r.json()["error"]["code"] for r in responses if r.status_code == 409}
        assert codes == {"skill.version_conflict"}
        assert await _versions(real_db, skill_id) == 2


async def test_two_skills_of_one_name_have_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await _owner(make_real_client, real_db)
    for n in range(ROUNDS):
        body = {"name": f"same-{n}", "description": "d", "content": "c"}
        responses = await asyncio.gather(*(owner.post(SKILLS, json=body) for _ in range(3)))
        assert sorted(r.status_code for r in responses) == [201, 409, 409]
        codes = {r.json()["error"]["code"] for r in responses if r.status_code == 409}
        assert codes == {"skill.name_taken"}
    async with real_db.database.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Skill)) == ROUNDS


async def test_two_settings_of_an_agents_skills_have_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    owner = await _owner(make_real_client, real_db)
    connection = await make_connection(owner, openai_stub)
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
            }
        )
        agent = await AgentService(session).create(await actor_of(session, boss), body)
        await session.commit()
    first, second = await _skill(owner, "first"), await _skill(owner, "second")
    url = f"/api/agents/{agent.id}/skills"
    for _ in range(ROUNDS):
        version = (await owner.get(url)).json()["version"]
        responses = await asyncio.gather(
            owner.put(url, json={"skill_ids": [first], "version": version}),
            owner.put(url, json={"skill_ids": [second], "version": version}),
        )
        assert sorted(r.status_code for r in responses) == [200, 409]
        winner = next(r for r in responses if r.status_code == 200).json()
        async with real_db.database.session_factory() as session:
            stored = await session.scalars(
                select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent.id)
            )
            assert [str(s) for s in stored] == [winner["skills"][0]["id"]]
