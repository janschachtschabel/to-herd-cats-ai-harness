"""Agents as the API manages them (plan M5 task 5): `agent.manage` only (owner and
admin), everyone else 404; the connection and the responsible person checked; versions;
an agent that talked is not deleted; audit without the instructions. The profile for
people with `ai.use`; a run and its events for whom it concerns."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.agents.models import StopReason
from app.modules.audit.models import AuditLog
from tests.factories_agents import Bench, assign_default, make_connection

AGENTS = "/api/agents"


def body(bench: Bench, **fields: Any) -> dict[str, Any]:
    return {
        "name": "Bea",
        "instructions": "Secret instructions",
        "connection_id": str(bench.connection.id),
        "model": "m1",
        "responsible_user_id": bench.people.id("admin"),
        **fields,
    }


async def test_only_agent_managers_manage_agents(bench: Bench) -> None:
    created = await bench.people.admin.post(AGENTS, json=body(bench))
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["status"] == "draft" and agent["version"] == 1
    mine = await bench.people.alice.get(AGENTS)  # with ai.use: her own personal agents
    assert mine.status_code == 200 and mine.json()["items"] == []
    assert (await bench.people.gast.get(AGENTS)).status_code == 404
    for who in ("alice", "gast"):
        client: AsyncClient = getattr(bench.people, who)
        for method, url, payload in (
            ("POST", AGENTS, body(bench)),
            ("GET", f"{AGENTS}/{agent['id']}", None),
            ("PATCH", f"{AGENTS}/{agent['id']}", {"name": "X", "version": 1}),
            ("DELETE", f"{AGENTS}/{agent['id']}?version=1", None),
        ):
            r = await client.request(method, url, json=payload)
            assert r.status_code == 404, (who, method, url)
            assert r.json()["error"]["code"] == "agent.not_found"
    listed = (await bench.people.admin.get(AGENTS)).json()
    assert {a["name"] for a in listed["items"]} == {"Ava", "Bea"}


async def test_changes_need_the_version_and_are_audited(bench: Bench) -> None:
    agent = (await bench.people.admin.post(AGENTS, json=body(bench))).json()
    url = f"{AGENTS}/{agent['id']}"
    stale = await bench.people.admin.patch(url, json={"name": "B2", "version": 7})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "agent.version_conflict"
    changed = await bench.people.admin.patch(
        url, json={"status": "active", "instructions": "New secret", "version": 1}
    )
    assert changed.status_code == 200 and changed.json()["version"] == 2
    rows = (
        await bench.session.scalars(
            select(AuditLog).where(AuditLog.target_id == agent["id"]).order_by(AuditLog.id)
        )
    ).all()
    assert [r.action for r in rows] == ["agent.created", "agent.updated"]
    text = " ".join(str(r.details) for r in rows)
    assert "secret" not in text.lower()
    assert rows[1].details["instructions_chars"] == len("New secret")


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"model": "unknown"}, "ai.model_unknown"),
        ({"responsible_user_id": "gast"}, "agent.responsible_invalid"),
        ({"max_steps": 26}, None),
        ({"instructions": "x" * 20_001}, None),
    ],
)
async def test_what_an_agent_needs(bench: Bench, fields: dict[str, Any], code: str | None) -> None:
    if fields.get("responsible_user_id") == "gast":
        fields = {"responsible_user_id": bench.people.id("gast")}
    r = await bench.people.admin.post(AGENTS, json=body(bench, **fields))
    assert r.status_code == 422, r.text
    if code is not None:
        assert r.json()["error"]["code"] == code


async def test_an_embedding_connection_is_no_agents(bench: Bench) -> None:
    embedding = await make_connection(
        bench.people.admin, bench.stub, name="Emb", purpose="embedding"
    )
    r = await bench.people.admin.post(AGENTS, json=body(bench, connection_id=embedding["id"]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "ai.connection_not_chat"


async def test_an_agent_that_talked_stays(bench: Bench) -> None:
    url = f"{AGENTS}/{bench.agent.id}"
    r = await bench.people.admin.delete(f"{url}?version={bench.agent.version}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "agent.in_use"
    fresh = (await bench.people.admin.post(AGENTS, json=body(bench))).json()
    gone = await bench.people.admin.delete(f"{AGENTS}/{fresh['id']}?version=1")
    assert gone.status_code == 204
    deleting = await bench.people.admin.delete(
        f"/api/ai/connections/{bench.connection.id}?version={bench.connection.version}"
    )
    assert deleting.status_code == 409  # the agent still talks to it


async def test_the_profile_for_people_with_ai(bench: Bench) -> None:
    url = f"{AGENTS}/{bench.agent.id}/profile"
    seen = await bench.people.alice.get(url)
    assert seen.status_code == 200
    assert seen.json() == {
        "id": str(bench.agent.id),
        "name": "Ava",
        "intro": "Answers questions from the wiki.",
        "status": "active",
        "kind": "internal",
    }
    assert (await bench.people.gast.get(url)).status_code == 404
    draft = (await bench.people.admin.post(AGENTS, json=body(bench))).json()
    hidden = await bench.people.alice.get(f"{AGENTS}/{draft['id']}/profile")
    assert hidden.status_code == 404
    await assign_default(bench.people.admin, None)
    assert (await bench.people.alice.get(url)).status_code == 404


async def test_a_run_for_whom_it_concerns(bench: Bench) -> None:
    posted = await bench.say("Hi")
    assert await bench.run_next() == StopReason.COMPLETED
    url = f"/api/runs/{posted['agent_run']['id']}"
    mine = await bench.people.alice.get(url)
    assert mine.status_code == 200 and mine.json()["stop_reason"] == "completed"
    run = mine.json()
    assert run["state"] == "done" and run["trigger_message_id"] == posted["id"]
    assert (run["attempt"], run["steps"], run["agent_id"]) == (1, 1, str(bench.agent.id))
    assert run["created_at"] <= run["started_at"] <= run["finished_at"]
    assert (await bench.people.admin.get(url)).status_code == 200  # responsible, manager
    assert (await bench.people.bob.get(url)).status_code == 404
    assert (await bench.people.bob.get(f"{url}/events")).status_code == 404
    events = (await bench.people.alice.get(f"{url}/events?limit=1")).json()
    assert len(events["items"]) == 1 and events["next_cursor"]
    rest = await bench.people.alice.get(f"{url}/events?cursor={events['next_cursor']}")
    kinds = [events["items"][0]["kind"], *(e["kind"] for e in rest.json()["items"])]
    assert sorted(kinds) == ["model_call", "stop"]


async def test_an_agent_names_its_responsible_person(bench: Bench) -> None:
    """Task 7's concern: the dialog shows the name without the people list's pages."""
    admin = bench.people.users["admin"]
    created = (await bench.people.admin.post(AGENTS, json=body(bench))).json()
    assert created["responsible_name"] == admin.name
    url = f"{AGENTS}/{created['id']}"
    changed = await bench.people.admin.patch(
        url, json={"responsible_user_id": bench.people.id("alice"), "version": 1}
    )
    assert changed.json()["responsible_name"] == bench.people.users["alice"].name
    assert (await bench.people.admin.get(url)).json()["responsible_name"] == "Alice"
    listed = (await bench.people.admin.get(AGENTS)).json()["items"]
    assert {a["name"]: a["responsible_name"] for a in listed} == {"Ava": admin.name, "Bea": "Alice"}
