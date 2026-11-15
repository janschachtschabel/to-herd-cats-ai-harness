"""Personal agents (plan M6 decision 13, task 10; spec 8.1): a person with
`agent.create_personal` (everyone with `ai.use`, while the organisation allows it)
creates, edits, pauses and deletes their own agents through `/api/agents`. A
personal agent belongs to its owner (responsible for it too), is a member only of the
owner's personal space, has at most level 2, uses the owner's connection and model,
and is limited per person (`HERD_AI_PERSONAL_AGENTS_MAX`)."""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.principal import PrincipalType
from app.modules.agents.models import Agent
from app.modules.audit.models import AuditLog
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from tests.factories_agents import Bench

AGENTS = "/api/agents"
SWITCH = "/api/ai/assignments/personal-agents"


async def create(client: AsyncClient, **fields: Any) -> Response:
    return await client.post(AGENTS, json={"name": "Pia", "personal": True, **fields})


async def created(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    r = await create(client, **fields)
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def switch(bench: Bench, enabled: bool) -> Response:
    version = (await bench.people.admin.get("/api/ai/assignments")).json()["version"]
    return await bench.people.admin.put(SWITCH, json={"enabled": enabled, "version": version})


async def permissions(client: AsyncClient) -> list[str]:
    found: list[str] = (await client.get("/api/auth/me")).json()["permissions"]
    return found


async def memberships(bench: Bench, agent_id: object) -> list[tuple[SpaceKind, object, str]]:
    stmt = (
        select(Space.kind, Space.owner_user_id, SpaceMember.role)
        .join(Space, Space.id == SpaceMember.space_id)
        .where(SpaceMember.member_type == PrincipalType.AGENT, SpaceMember.member_id == agent_id)
    )
    return [(k, o, r) for k, o, r in await bench.session.execute(stmt)]


async def test_a_person_with_ai_creates_a_personal_agent(bench: Bench) -> None:
    assert "agent.create_personal" in await permissions(bench.people.alice)
    body = await created(bench.people.alice, instructions="Be kind.", status="active")
    alice = bench.people.users["alice"]
    assert body["owner_user_id"] == str(alice.id)
    assert body["responsible_user_id"] == str(alice.id) and body["responsible_name"] == "Alice"
    assert (body["connection_id"], body["model"]) == (str(bench.connection.id), "m1")
    assert body["level"] == 2 and body["status"] == "active"
    assert await memberships(bench, body["id"]) == [(SpaceKind.PERSONAL, alice.id, "editor")]
    audit = await bench.session.scalar(
        select(AuditLog).where(AuditLog.action == "agent.created", AuditLog.target_id == body["id"])
    )
    assert audit is not None and audit.details is not None
    assert audit.details["owner_user_id"] == str(alice.id)
    assert "Be kind." not in str(audit.details)


async def test_a_personal_agent_takes_only_its_owners_connection_and_model(
    bench: Bench,
) -> None:
    alice = bench.people.alice
    same = {"connection_id": str(bench.connection.id), "model": "m1"}
    assert (await create(alice, **same)).status_code == 201
    other = await create(alice, connection_id=str(bench.connection.id), model="m2")
    assert other.status_code == 422 and other.json()["error"]["code"] == "ai.model_unknown"
    elsewhere = await create(
        alice, connection_id="0190f0f0-0000-7000-8000-000000000000", model="m1"
    )
    assert elsewhere.json()["error"]["code"] == "ai.connection_not_found"


async def test_a_personal_agent_has_at_most_level_two_and_its_owner_responsible(
    bench: Bench,
) -> None:
    alice = bench.people.alice
    high = await create(alice, level=3)
    assert high.status_code == 403 and high.json()["error"]["code"] == "agent.level_denied"
    bob = await create(alice, responsible_user_id=bench.people.id("bob"))
    assert bob.status_code == 422 and bob.json()["error"]["code"] == "agent.responsible_invalid"
    body = await created(alice)
    up = await alice.patch(f"{AGENTS}/{body['id']}", json={"level": 3, "version": 1})
    assert up.status_code == 403 and up.json()["error"]["code"] == "agent.level_denied"
    admin = await bench.people.admin.patch(
        f"{AGENTS}/{body['id']}", json={"level": 3, "version": 1}
    )
    assert admin.status_code == 403  # an admin neither
    moved = await alice.patch(
        f"{AGENTS}/{body['id']}",
        json={"responsible_user_id": bench.people.id("bob"), "version": 1},
    )
    assert moved.status_code == 422


async def test_without_the_right_there_is_nothing_to_create(bench: Bench) -> None:
    gast = await create(bench.people.gast)
    assert gast.status_code == 404 and gast.json()["error"]["code"] == "agent.not_found"
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{bench.people.id('bob')}",
        json={"no_ai": True, "version": None},
    )
    assert r.status_code == 200
    assert (await create(bench.people.bob)).status_code == 404
    assert "agent.create_personal" not in await permissions(bench.people.bob)
    count = await bench.session.scalar(
        select(func.count()).select_from(Agent).where(Agent.owner_user_id.is_not(None))
    )
    assert count == 0


async def test_admins_can_switch_personal_agents_off(bench: Bench) -> None:
    switched = await switch(bench, False)
    assert switched.status_code == 200 and switched.json()["personal_agents"] is False
    assert "agent.create_personal" not in await permissions(bench.people.alice)
    assert "ai.use" in await permissions(bench.people.alice)
    off = await create(bench.people.alice)
    assert off.status_code == 403 and off.json()["error"]["code"] == "agent.personal_disabled"
    assert (await switch(bench, True)).json()["personal_agents"] is True
    assert "agent.create_personal" in await permissions(bench.people.alice)
    assert (await create(bench.people.alice)).status_code == 201
    stale = await bench.people.admin.put(SWITCH, json={"enabled": False, "version": 1})
    assert stale.status_code == 409
    member = await bench.people.alice.put(SWITCH, json={"enabled": False, "version": 1})
    assert member.status_code == 404 and member.json()["error"]["code"] == "ai.not_found"
    audit = await bench.session.scalar(
        select(func.count()).where(AuditLog.action == "ai_assignment.personal_agents_set")
    )
    assert audit == 2


async def test_each_person_has_a_limit(bench: Bench, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ai_personal_agents_max", 2)
    for name in ("One", "Two"):
        await created(bench.people.alice, name=name)
    third = await create(bench.people.alice, name="Three")
    assert third.status_code == 409 and third.json()["error"]["code"] == "agent.personal_limit"
    assert (await create(bench.people.bob)).status_code == 201  # per person


async def test_owners_manage_their_own_agents_only(bench: Bench) -> None:
    alice, bob = bench.people.alice, bench.people.bob
    mine = await created(alice, status="active")
    path = f"{AGENTS}/{mine['id']}"
    listed = (await alice.get(AGENTS)).json()["items"]
    assert [a["id"] for a in listed] == [mine["id"]]  # not the organisation's Ava
    assert (await alice.get(f"{AGENTS}/{bench.agent.id}")).status_code == 404
    assert (await bob.get(AGENTS)).json()["items"] == []
    for method in ("get", "patch", "delete"):
        kwargs: dict[str, Any] = {}
        if method == "patch":
            kwargs = {"json": {"name": "Mine now", "version": 1}}
        if method == "delete":
            kwargs = {"params": {"version": 1}}
        r = await getattr(bob, method)(path, **kwargs)
        assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found", method
    paused = await alice.patch(path, json={"status": "paused", "version": 1})
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    stale = await alice.patch(path, json={"name": "X", "version": 1})
    assert stale.status_code == 409
    tools = await alice.get(f"{path}/tools")
    assert tools.status_code == 200 and tools.json()["max_level"] == 2  # never offered more
    shown = await bench.people.admin.get(f"{path}/tools")
    assert shown.json()["max_level"] == 2  # an admin neither
    tightened = await alice.put(
        f"{path}/tools", json={"tools": [{"tool": "search", "policy": "block"}], "version": 2}
    )
    assert tightened.status_code == 200, tightened.text
    assert (await alice.delete(path, params={"version": 3})).status_code == 204
    assert await memberships(bench, mine["id"]) == []


async def test_an_admin_sees_every_agent_and_opening_a_personal_one_is_noted(
    bench: Bench,
) -> None:
    mine = await created(bench.people.alice, instructions="Private notes.")

    async def noted() -> int:
        stmt = select(func.count()).where(
            AuditLog.action == "agent.admin_access", AuditLog.target_id == mine["id"]
        )
        return int(await bench.session.scalar(stmt) or 0)

    listed = (await bench.people.admin.get(AGENTS)).json()["items"]
    assert {a["id"] for a in listed} == {str(bench.agent.id), mine["id"]}
    assert await noted() == 1
    opened = await bench.people.admin.get(f"{AGENTS}/{mine['id']}")
    assert opened.status_code == 200 and opened.json()["instructions"] == "Private notes."
    runs = await bench.people.admin.get(f"{AGENTS}/{mine['id']}/runs")
    assert runs.status_code == 200
    assert await noted() == 1  # once per admin, agent and day
    await bench.people.alice.get(f"{AGENTS}/{mine['id']}")
    await bench.people.admin.get(f"{AGENTS}/{bench.agent.id}")
    assert await noted() == 1  # not for the owner, not for organisation agents
    entry = await bench.session.scalar(
        select(AuditLog).where(AuditLog.action == "agent.admin_access")
    )
    assert entry is not None and entry.actor_id == bench.people.users["admin"].id
