"""External agents for tests (plan M8 task 4): `make_external` creates one over the
API (the admin manages agents; Alice answers for it) and makes it a member of the
work space; `agent_token` issues one of its tokens (clear text in `secret`)."""

import uuid
from typing import Any

from httpx import AsyncClient

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import Agent
from app.modules.spaces.repository import SpaceRepository
from tests.factories_writing import Work


async def make_external(
    work: Work, name: str = "Codi", role: SpaceRole | None = SpaceRole.EDITOR, **fields: Any
) -> Agent:
    bench = work.bench
    body = {
        "name": name,
        "kind": "external",
        "intro": "Works from outside.",
        "responsible_user_id": str(bench.people.users["alice"].id),
        "status": "active",
        **fields,
    }
    r = await work.admin.post("/api/agents", json=body)
    assert r.status_code == 201, r.text
    agent = await bench.session.get(Agent, uuid.UUID(r.json()["id"]))
    assert agent is not None
    if role is not None:
        repo = SpaceRepository(bench.session)
        await repo.set_member(work.space.id, Principal.agent(agent.id), role)
    return agent


async def agent_token(client: AsyncClient, agent: Agent, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Codex", "mode": "write", "expires_in_days": 30}
    body.update(fields)
    r = await client.post(f"/api/agents/{agent.id}/tokens", json=body)
    assert r.status_code == 201, r.text
    made: dict[str, Any] = r.json()
    return made
