"""Agents as principals (plan M5 task 5, Review Focus 2): a DM of one person with one
agent, only with `ai.use`; a message there queues a run, or stays without one and
says why; agents in the directory and as space members only for people who may see
them; `access.changed` when what decides `ai.use` changes (ruling c)."""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.outbox import EventOutbox
from app.modules.agents.models import AgentStatus, Run
from app.modules.ai.models import AiConnection
from app.modules.groups.models import Group, GroupMember
from app.modules.users.models import User
from tests.factories_agents import (
    Bench,
    assign_default,
    make_agent,
    make_connection,
    open_agent_dm,
)

DMS = "/api/dms"


async def _runs(bench: Bench) -> int:
    return int(await bench.session.scalar(select(func.count()).select_from(Run)) or 0)


async def test_a_dm_with_an_agent_is_one_person_and_the_agent(bench: Bench) -> None:
    again = await open_agent_dm(bench.people.alice, bench.agent)
    assert again["id"] == bench.dm["id"]
    types = sorted((p["type"], p["name"]) for p in bench.dm["participants"])
    assert types == [("agent", "Ava"), ("user", "Alice")]
    both = await bench.people.alice.post(
        DMS, json={"agent_id": str(bench.agent.id), "user_ids": [bench.people.id("bob")]}
    )
    assert both.status_code == 422 and both.json()["error"]["code"] == "dm.agent_pair_only"
    bob = await open_agent_dm(bench.people.bob, bench.agent)
    assert bob["id"] != bench.dm["id"]


@pytest.mark.parametrize("who", ["gast", "no_ai"])
async def test_without_ai_no_way_to_an_agent(bench: Bench, who: str) -> None:
    if who == "no_ai":
        await assign_default(bench.people.admin, None)
        who = "alice"
    client = getattr(bench.people, who)
    opened = await client.post(DMS, json={"agent_id": str(bench.agent.id)})
    unknown = await client.post(DMS, json={"agent_id": str(uuid.uuid4())})
    expected = (403, "dm.guest_cannot_open") if who == "gast" else (404, "agent.not_found")
    for answer in (opened, unknown):  # the same for a real agent and for none
        assert (answer.status_code, answer.json()["error"]["code"]) == expected
    assert (await client.get(f"/api/agents/{bench.agent.id}/profile")).status_code == 404
    directory = await client.get("/api/directory?q=Ava")  # guests may not read it at all
    assert directory.status_code != 200 or directory.json()["items"] == []


async def test_a_draft_agent_cannot_be_addressed(bench: Bench) -> None:
    draft = await make_agent(bench.session, bench.people, bench.connection.id, status="draft")
    r = await bench.people.alice.post(DMS, json={"agent_id": str(draft.id)})
    assert r.status_code == 404
    found = (await bench.people.alice.get("/api/directory?type=agent")).json()["items"]
    assert [a["name"] for a in found] == ["Ava"]


async def test_after_losing_ai_a_message_starts_no_run(bench: Bench) -> None:
    await assign_default(bench.people.admin, None)
    posted = await bench.say("Still there?")
    assert posted["agent_run"] == {
        "id": None,
        "reason": "ai.unavailable",
        "agent_id": str(bench.agent.id),
    }
    assert posted["body_md"] == "Still there?"  # the message itself is kept
    assert await _runs(bench) == 0


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("paused", "agent.paused"),
        ("responsible", "agent.responsible_inactive"),
        ("connection", "agent.connection_unavailable"),
        ("model", "agent.connection_unavailable"),
    ],
)
async def test_an_agent_that_may_not_run_says_why(bench: Bench, change: str, reason: str) -> None:
    """The agent has a connection of its own, so the person keeps `ai.use`."""
    own = await make_connection(bench.people.admin, bench.stub, name="Own", models=["m1", "m2"])
    agent = await make_agent(bench.session, bench.people, own["id"], name="Otto")
    dm = await open_agent_dm(bench.people.alice, agent)
    connection = await bench.session.get(AiConnection, own["id"])
    assert connection is not None
    if change == "paused":
        agent.status = AgentStatus.PAUSED
    elif change == "responsible":
        bench.people.users["admin"].is_active = False
    elif change == "connection":
        connection.enabled = False
    else:
        connection.models = ["m2"]
    await bench.session.flush()
    posted = await bench.say("Hi", dm=str(dm["id"]))
    assert posted["agent_run"] == {"id": None, "reason": reason, "agent_id": str(agent.id)}
    assert await _runs(bench) == 0


async def test_a_reply_in_a_thread_starts_no_run(bench: Bench) -> None:
    top = await bench.say("Top")
    r = await bench.people.alice.post(
        f"/api/conversations/{bench.dm_id}/messages",
        json={"body_md": "Reply", "parent_id": top["id"]},
    )
    assert r.json()["agent_run"] == {
        "id": None,
        "reason": "run.thread_reply",
        "agent_id": str(bench.agent.id),
    }
    assert await _runs(bench) == 1


async def test_a_message_elsewhere_has_no_run(bench: Bench) -> None:
    dm = (await bench.people.alice.post(DMS, json={"user_ids": [bench.people.id("bob")]})).json()
    r = await bench.people.alice.post(
        f"/api/conversations/{dm['id']}/messages", json={"body_md": "Hi Bob"}
    )
    assert r.status_code == 201 and r.json()["agent_run"] is None


async def test_agents_as_space_members(bench: Bench) -> None:
    made = await bench.people.alice.post("/api/spaces", json={"kind": "team", "name": "Team"})
    space = made.json()
    url = f"/api/spaces/{space['id']}/members"
    member = {"member_type": "agent", "member_id": str(bench.agent.id), "role": "viewer"}
    added = await bench.people.alice.put(url, json=member)
    assert added.status_code == 200 and added.json()["name"] == "Ava"
    listed = (await bench.people.alice.get(url)).json()["items"]
    assert ("agent", "Ava") in [(m["member_type"], m["name"]) for m in listed]
    await assign_default(bench.people.admin, None)
    hidden = (await bench.people.alice.get(url)).json()["items"]
    assert all(m["member_type"] != "agent" for m in hidden)
    again = await bench.people.alice.put(url, json=member)
    assert again.status_code == 404 and again.json()["error"]["code"] == "agent.not_found"


async def test_without_ai_an_agent_member_cannot_be_removed_or_told_apart(
    bench: Bench,
) -> None:
    """Finding 8: a space admin without `ai.use` gets the same 404 for a real agent
    member as for an invented id, and the membership stays."""
    made = await bench.people.alice.post("/api/spaces", json={"kind": "team", "name": "Team"})
    url = f"/api/spaces/{made.json()['id']}/members"
    member = {"member_type": "agent", "member_id": str(bench.agent.id), "role": "viewer"}
    assert (await bench.people.alice.put(url, json=member)).status_code == 200
    await assign_default(bench.people.admin, None)
    answers = [
        await bench.people.alice.delete(f"{url}/agent/{agent_id}")
        for agent_id in (bench.agent.id, uuid.uuid4())
    ]
    for answer in answers:
        assert answer.status_code == 404
        assert answer.json()["error"]["code"] == "spaces.member_not_found"
    listed = (await bench.people.admin.get(url)).json()["items"]
    assert ("agent", "Ava") in [(m["member_type"], m["name"]) for m in listed]


async def test_a_draft_agent_is_no_member_for_those_who_may_not_manage_agents(
    bench: Bench,
) -> None:
    """Finding 9: adding a draft answers like an unknown agent, without its name."""
    draft = await make_agent(
        bench.session, bench.people, bench.connection.id, name="SecretDraftBot", status="draft"
    )
    made = await bench.people.alice.post("/api/spaces", json={"kind": "team", "name": "Team"})
    url = f"/api/spaces/{made.json()['id']}/members"
    member = {"member_type": "agent", "member_id": str(draft.id), "role": "viewer"}
    r = await bench.people.alice.put(url, json=member)
    assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found"
    assert "SecretDraftBot" not in r.text
    by_manager = await bench.people.admin.put(url, json=member)
    assert by_manager.status_code == 200 and by_manager.json()["name"] == "SecretDraftBot"


async def _access_changed(bench: Bench) -> set[str]:
    rows = (
        await bench.session.scalars(select(EventOutbox).where(EventOutbox.type == "access.changed"))
    ).all()
    return {r.payload["user_id"] for r in rows}


async def test_what_decides_ai_use_announces_access_changed(bench: Bench) -> None:
    """Ruling (c): the default, the group assignments and disabling a connection tell
    the people concerned to reload their rights."""
    active = {str(u) for u in (await bench.session.scalars(select(User.id))).all()}
    await bench.session.execute(EventOutbox.__table__.delete())
    await assign_default(bench.people.admin, None)
    assert await _access_changed(bench) == active

    group = Group(org_id=bench.agent.org_id, name="AI")
    bench.session.add(group)
    await bench.session.flush()
    bench.session.add(
        GroupMember(
            group_id=group.id,
            member_type="user",
            member_id=bench.people.users["bob"].id,
        )
    )
    await bench.session.flush()
    await bench.session.execute(EventOutbox.__table__.delete())
    version = (await bench.people.admin.get("/api/ai/assignments")).json()["version"]
    items = [{"group_id": str(group.id), "connection_id": str(bench.connection.id), "model": "m1"}]
    r = await bench.people.admin.put(
        "/api/ai/assignments/groups", json={"items": items, "version": version}
    )
    assert r.status_code == 200, r.text
    assert await _access_changed(bench) == {bench.people.id("bob")}

    await bench.session.execute(EventOutbox.__table__.delete())
    r = await bench.people.admin.patch(
        f"/api/ai/connections/{bench.connection.id}",
        json={"enabled": False, "version": bench.connection.version},
    )
    assert r.status_code == 200, r.text
    assert await _access_changed(bench) == active
