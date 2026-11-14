"""Who reaches a personal agent, and when it stops (plan M6 task 10): only its owner
talks to it (DM, profile, directory hide it from everyone else, admins too); it stays
in its owner's personal space (adding it anywhere else is refused, also for admins);
its runs are billed to the owner; and it stops working when the owner loses AI, is
deactivated, the organisation switches personal agents off, or the owner's model is
no longer the agent's."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.modules.agents.models import Agent, StopReason
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import Refusal, agent_refusal, refusal
from app.modules.ai.models import UsageRecord
from app.modules.spaces.models import SpaceKind
from tests.factories_agents import Bench, assign_default, make_connection, open_agent_dm
from tests.factories_spaces import MakeSpace, personal_space_of
from tests.factories_wiki import new_page, publish
from tests.test_access import actor_of
from tests.test_personal_agents import AGENTS, created, switch


async def pia(bench: Bench) -> Agent:
    """Alice's active personal agent."""
    body = await created(bench.people.alice, status="active")
    agent = await bench.session.get(Agent, body["id"])
    assert agent is not None
    return agent


async def ask(bench: Bench, dm_id: str, text: str = "Hi") -> dict[str, Any]:
    return await bench.say(text, dm=dm_id)


async def test_only_the_owner_talks_to_it(bench: Bench) -> None:
    agent = await pia(bench)
    dm = await open_agent_dm(bench.people.alice, agent)
    posted = await ask(bench, dm["id"])
    assert posted["agent_run"]["id"] is not None
    assert await bench.run_next() == StopReason.COMPLETED
    usage = (await bench.session.scalars(select(UsageRecord.user_id))).all()
    assert usage and set(usage) == {bench.people.users["alice"].id}  # billed to the owner
    for who in ("bob", "admin"):
        client: AsyncClient = getattr(bench.people, who)
        r = await client.post("/api/dms", json={"agent_id": str(agent.id)})
        assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found", who
        profile = await client.get(f"{AGENTS}/{agent.id}/profile")
        assert profile.status_code == 404, who
        found = await client.get("/api/directory", params={"q": "Pia", "type": "agent"})
        assert found.json()["items"] == [], who
    mine = await bench.people.alice.get("/api/directory", params={"q": "Pia", "type": "agent"})
    assert [e["id"] for e in mine.json()["items"]] == [str(agent.id)]
    assert (await bench.people.alice.get(f"{AGENTS}/{agent.id}/profile")).status_code == 200


async def test_it_stays_in_its_owners_personal_space(bench: Bench, make_space: MakeSpace) -> None:
    agent = await pia(bench)
    users = bench.people.users
    roster = [(users["alice"], SpaceRole.ADMIN), (users["bob"], SpaceRole.ADMIN)]
    team = await make_space(SpaceKind.TEAM, members=roster)
    body = {"member_type": "agent", "member_id": str(agent.id), "role": "viewer"}
    for who, code in (
        ("alice", "agent.personal_space_only"),
        ("admin", "agent.personal_space_only"),
        ("bob", "agent.not_found"),
    ):
        r = await getattr(bench.people, who).put(f"/api/spaces/{team.id}/members", json=body)
        expected = 404 if code == "agent.not_found" else 422
        assert r.status_code == expected and r.json()["error"]["code"] == code, (who, r.text)
    personal = await personal_space_of(bench.session, users["bob"])
    r = await bench.people.admin.put(f"/api/spaces/{personal.id}/members", json=body)
    assert r.status_code == 409  # personal spaces keep their members


async def test_it_stops_when_its_owner_loses_ai(bench: Bench) -> None:
    agent = await pia(bench)
    dm = await open_agent_dm(bench.people.alice, agent)
    queued = await ask(bench, dm["id"])
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id('alice')}",
        json={"no_ai": True, "version": None},
    )
    assert r.status_code == 200
    # The agent itself stands refused, whoever would ask (`standing.agent_refusal`).
    assert await agent_refusal(bench.session, agent.org_id, agent) == Refusal.AI_UNAVAILABLE
    assert await bench.run_next() == StopReason.RIGHTS_REVOKED
    run = await bench.run_of(queued["agent_run"]["id"])
    assert run.stop_reason == StopReason.RIGHTS_REVOKED
    assert bench.stub.state.log == []


async def test_it_stops_when_its_owner_is_deactivated(bench: Bench) -> None:
    agent = await pia(bench)
    dm = await open_agent_dm(bench.people.alice, agent)
    await ask(bench, dm["id"])
    r = await bench.people.admin.post(f"/api/admin/users/{bench.people.id('alice')}/deactivate")
    assert r.status_code == 204, r.text
    assert await bench.run_next() == StopReason.RIGHTS_REVOKED
    assert bench.stub.state.log == []


async def test_it_stops_when_personal_agents_are_switched_off(bench: Bench) -> None:
    agent = await pia(bench)
    dm = await open_agent_dm(bench.people.alice, agent)
    assert (await switch(bench, False)).status_code == 200
    refused = await ask(bench, dm["id"])
    assert refused["agent_run"] == {
        "id": None,
        "reason": "agent.personal_disabled",
        "agent_id": str(agent.id),
    }
    assert (await switch(bench, True)).status_code == 200
    assert (await ask(bench, dm["id"], "Again"))["agent_run"]["id"] is not None


async def test_it_follows_its_owners_model_only_when_saved_again(bench: Bench) -> None:
    agent = await pia(bench)
    dm = await open_agent_dm(bench.people.alice, agent)
    other = await make_connection(bench.people.admin, bench.stub, name="Other", models=["m9"])
    await assign_default(bench.people.admin, None)
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id('alice')}",
        json={"target": {"connection_id": other["id"], "model": "m9"}, "version": None},
    )
    assert r.status_code == 200, r.text
    refused = await ask(bench, dm["id"])
    assert refused["agent_run"] == {
        "id": None,
        "reason": "agent.connection_unavailable",
        "agent_id": str(agent.id),
    }
    saved = await bench.people.alice.patch(f"{AGENTS}/{agent.id}", json={"version": 1})
    assert saved.status_code == 200, saved.text
    assert (saved.json()["connection_id"], saved.json()["model"]) == (other["id"], "m9")
    assert (await ask(bench, dm["id"], "Now?"))["agent_run"]["id"] is not None


async def test_a_run_for_anyone_but_its_owner_never_starts_nor_runs(
    bench: Bench, make_space: MakeSpace
) -> None:
    """Defence in depth for later triggers (mentions, plan M6 task 8): someone else
    is refused, and a run asked by someone else ends before any call."""
    agent = await pia(bench)
    bob = bench.people.users["bob"]
    assert await refusal(bench.session, await actor_of(bench.session, bob), agent) == (
        Refusal.NOT_FOUND
    )
    hall = await make_space(SpaceKind.OPEN)
    page = await publish(bench.people.admin, await new_page(bench.people.admin, hall.id, "Hall"))
    thread = (await bench.people.bob.get(f"/api/pages/{page['id']}/thread")).json()
    said = await bench.people.bob.post(
        f"/api/conversations/{thread['id']}/messages", json={"body_md": "@Pia?"}
    )
    assert said.status_code == 201, said.text
    await RunRepository(bench.session, agent.org_id).enqueue(
        agent.id, bob.id, uuid.UUID(thread["id"]), uuid.UUID(said.json()["id"])
    )
    assert await bench.run_next() == StopReason.RIGHTS_REVOKED
    assert bench.stub.state.log == []
