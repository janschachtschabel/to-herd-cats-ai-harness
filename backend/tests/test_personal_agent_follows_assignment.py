"""A personal agent's stored connection and model follow its owner's assignment
(review M6 2, finding 5): changing a person's, a group's or the default assignment
writes the owner's new target onto their personal agents in the same transaction.
So a claim counts the agent's runs against the connection they call
(`max_concurrency`), and the old connection, which nothing uses any more, can be
deleted. A run still resolves the owner's assignment when it starts."""

from typing import Any

from app.modules.agents.executor_repository import claim
from app.modules.agents.models import Agent
from tests.factories_agents import (
    LEASE,
    Bench,
    assign_default,
    make_agent,
    make_connection,
    open_agent_dm,
)
from tests.factories_groups import MakeGroup
from tests.test_personal_agent_reach import ask, pia


async def _assign(bench: Bench, who: str, connection: dict[str, Any], model: str) -> None:
    listed = (await bench.people.admin.get("/api/ai/assignments/users")).json()["items"]
    version = next((u["version"] for u in listed if u["user_id"] == bench.people.id(who)), None)
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id(who)}",
        json={"target": {"connection_id": connection["id"], "model": model}, "version": version},
    )
    assert r.status_code == 200, r.text


async def _stored(bench: Bench, agent: Agent) -> tuple[str, str]:
    await bench.session.refresh(agent)
    return str(agent.connection_id), agent.model


async def test_the_owners_connection_keeps_its_max_concurrency(bench: Bench) -> None:
    agent = await pia(bench)  # stored: the bench's connection
    mine = await open_agent_dm(bench.people.alice, agent)
    other = await make_connection(
        bench.people.admin, bench.stub, name="Other", models=["m9"], max_concurrency=1
    )
    await assign_default(bench.people.admin, None)
    for who in ("alice", "bob"):
        await _assign(bench, who, other, "m9")
    otto = await make_agent(bench.session, bench.people, other["id"], name="Otto", model="m9")
    theirs = await open_agent_dm(bench.people.bob, otto)
    first = await bench.say("Hi", who="bob", dm=str(theirs["id"]))
    async with bench.unit()() as session:
        running = await claim(session, LEASE)
    assert running is not None and str(running.id) == first["agent_run"]["id"]
    asked = await ask(bench, mine["id"])  # Alice's personal agent: it calls "Other" too
    assert asked["agent_run"]["id"]
    async with bench.unit()() as session:
        second = await claim(session, LEASE)
    assert second is None, "two runs on a connection whose max_concurrency is 1"


async def test_a_person_assignment_moves_the_agent_and_frees_the_old_connection(
    bench: Bench,
) -> None:
    old = await make_connection(bench.people.admin, bench.stub, name="Old", models=["m5"])
    await _assign(bench, "alice", old, "m5")
    agent = await pia(bench)
    assert await _stored(bench, agent) == (old["id"], "m5")
    other = await make_connection(bench.people.admin, bench.stub, name="Other", models=["m9"])
    await _assign(bench, "alice", other, "m9")
    assert await _stored(bench, agent) == (other["id"], "m9")
    version = (await bench.people.admin.get(f"/api/ai/connections/{old['id']}")).json()["version"]
    r = await bench.people.admin.delete(f"/api/ai/connections/{old['id']}?version={version}")
    assert r.status_code == 204, r.text


async def test_the_default_and_removing_a_person_assignment_move_it_too(bench: Bench) -> None:
    agent = await pia(bench)
    first = await _stored(bench, agent)
    other = await make_connection(bench.people.admin, bench.stub, name="Other", models=["m1", "m9"])
    await _assign(bench, "alice", other, "m9")
    assert await _stored(bench, agent) == (other["id"], "m9")
    listed = await bench.people.admin.get("/api/ai/assignments/users")
    (row,) = [u for u in listed.json()["items"] if u["user_id"] == bench.people.id("alice")]
    r = await bench.people.admin.delete(
        f"/api/ai/assignments/users/{row['user_id']}?version={row['version']}"
    )
    assert r.status_code == 204, r.text
    assert await _stored(bench, agent) == first  # the default again
    await assign_default(bench.people.admin, other)
    assert (await _stored(bench, agent))[0] == other["id"]


async def test_an_owner_without_ai_keeps_what_was_stored(bench: Bench) -> None:
    agent = await pia(bench)
    first = await _stored(bench, agent)
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id('alice')}",
        json={"no_ai": True, "version": None},
    )
    assert r.status_code == 200, r.text
    assert await _stored(bench, agent) == first


async def test_a_group_assignment_moves_its_members_agents(
    bench: Bench, make_group: MakeGroup
) -> None:
    agent = await pia(bench)
    other = await make_connection(bench.people.admin, bench.stub, name="Other", models=["m9"])
    team = await make_group("Team", members=[bench.people.users["alice"]])
    version = (await bench.people.admin.get("/api/ai/assignments")).json()["version"]
    item = {"group_id": str(team.id), "connection_id": other["id"], "model": "m9"}
    r = await bench.people.admin.put(
        "/api/ai/assignments/groups", json={"items": [item], "version": version}
    )
    assert r.status_code == 200, r.text
    assert await _stored(bench, agent) == (other["id"], "m9")
