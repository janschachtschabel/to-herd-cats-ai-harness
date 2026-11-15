"""Plan M6 task 12: with a space, the directory offers the agents that are members of
it (the ones a mention there asks and a ticket there can be given to), to people with
`ai.use` only; never an agent outside the space, a draft, or someone else's personal
agent."""

from typing import Any

from httpx import AsyncClient

from app.modules.agents.models import AgentStatus
from tests.factories_agents import assign_default, make_agent
from tests.factories_spaces import personal_space_of
from tests.factories_writing import Work
from tests.test_personal_agents import created

DIRECTORY = "/api/directory"


async def _found(client: AsyncClient, **params: Any) -> list[dict[str, str]]:
    r = await client.get(DIRECTORY, params={"limit": 100, **params})
    assert r.status_code == 200, r.text
    items: list[dict[str, str]] = r.json()["items"]
    return items


async def test_a_space_offers_its_member_agents_beside_its_people(work: Work) -> None:
    bench = work.bench
    outsider = await make_agent(bench.session, bench.people, bench.connection.id, name="Olga")
    found = await _found(bench.people.alice, space_id=str(work.space.id))
    agents = [e for e in found if e["type"] == "agent"]
    assert agents == [
        {"type": "agent", "id": str(bench.agent.id), "name": "Ava", "kind": "internal"}
    ]
    assert str(bench.people.users["alice"].id) in {e["id"] for e in found if e["type"] == "user"}
    assert str(outsider.id) not in {e["id"] for e in found}
    only = await _found(bench.people.alice, space_id=str(work.space.id), type="agent")
    assert [e["id"] for e in only] == [str(bench.agent.id)]
    people = await _found(bench.people.alice, space_id=str(work.space.id), type="user")
    assert {e["type"] for e in people} == {"user"}
    # The private space has no agent member.
    assert await _found(bench.people.alice, space_id=str(work.private.id), type="agent") == []


async def test_no_agents_without_ai_use_and_no_drafts(work: Work) -> None:
    bench = work.bench
    bench.agent.status = AgentStatus.DRAFT
    await bench.session.flush()
    assert await _found(bench.people.alice, space_id=str(work.space.id), type="agent") == []
    bench.agent.status = AgentStatus.ACTIVE
    await bench.session.flush()
    await assign_default(bench.people.admin, None)  # nobody has `ai.use` now
    found = await _found(bench.people.alice, space_id=str(work.space.id))
    assert {e["type"] for e in found} == {"user"}


async def test_a_personal_agent_only_for_its_owner(work: Work) -> None:
    bench = work.bench
    body = await created(bench.people.alice, status="active", name="Pia")
    personal = await personal_space_of(bench.session, bench.people.users["alice"])
    mine = await _found(bench.people.alice, space_id=str(personal.id), type="agent")
    assert [e["id"] for e in mine] == [body["id"]]
    admin = await bench.people.admin.get(
        DIRECTORY, params={"space_id": str(personal.id), "type": "agent"}
    )
    assert admin.status_code == 404 or admin.json()["items"] == []
