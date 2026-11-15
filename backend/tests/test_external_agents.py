"""Plan M8 task 4 (decision 11): an external agent is a principal with memberships like
every agent, but it has no connection, no model and no runs in the system; it works
from outside through `/mcp` with an agent token. Only holders of `agent.manage`
create it, at level 2 at most, never as a personal agent. Mentions, DMs, ticket
assignments and automations start no run of it; a ticket assigned to it waits to be
picked up (`awaiting_pickup`), with no refusal notice in its thread."""

from typing import Any

from sqlalchemy import func, select

from app.modules.agents.run_models import Run
from app.modules.agents.standing import Refusal, agent_refusal
from app.modules.audit.models import AuditLog
from tests.factories_external_agents import make_external
from tests.factories_writing import Work

AGENTS = "/api/agents"


async def _runs(work: Work) -> int:
    return int(await work.bench.session.scalar(select(func.count()).select_from(Run)) or 0)


async def test_an_agent_manager_creates_an_external_agent_without_a_model(work: Work) -> None:
    alice = work.bench.people.users["alice"]
    agent = await make_external(work)
    shown = (await work.admin.get(f"{AGENTS}/{agent.id}")).json()
    assert shown["kind"] == "external"
    assert shown["connection_id"] is None and shown["model"] is None
    assert shown["responsible_user_id"] == str(alice.id) and shown["level"] == 2
    profile = (await work.bench.people.alice.get(f"{AGENTS}/{agent.id}/profile")).json()
    assert profile["kind"] == "external"
    (audit,) = (
        await work.bench.session.scalars(
            select(AuditLog).where(
                AuditLog.action == "agent.created", AuditLog.target_id == agent.id
            )
        )
    ).all()
    assert audit.details is not None and audit.details["kind"] == "external"


async def test_an_external_agent_takes_no_model_no_higher_level_and_is_nobodys_own(
    work: Work,
) -> None:
    alice = str(work.bench.people.users["alice"].id)
    base = {"name": "X", "kind": "external", "responsible_user_id": alice}
    wrong = [
        {"connection_id": str(work.bench.connection.id), "model": "m1"},
        {"level": 3},
        {"personal": True},
    ]
    for extra in wrong:
        r = await work.admin.post(AGENTS, json={**base, **extra})
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "agent.external_invalid"
    r = await work.admin.post(AGENTS, json={"name": "X", "kind": "external"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "agent.responsible_invalid"
    agent = await make_external(work)
    for change in (
        {"level": 3},
        {"connection_id": str(work.bench.connection.id), "model": "m1"},
    ):
        r = await work.admin.patch(f"{AGENTS}/{agent.id}", json={**change, "version": 1})
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "agent.external_invalid"
    r = await work.admin.patch(f"{AGENTS}/{agent.id}", json={"level": 1, "version": 1})
    assert r.status_code == 200 and r.json()["level"] == 1


async def test_only_agent_managers_create_external_agents(work: Work) -> None:
    alice = work.bench.people.users["alice"]
    body = {"name": "X", "kind": "external", "responsible_user_id": str(alice.id)}
    r = await work.bench.people.alice.post(AGENTS, json=body)
    assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found"


async def test_mentions_and_dms_start_no_run_of_an_external_agent(work: Work) -> None:
    agent = await make_external(work)
    bench = work.bench
    assert await agent_refusal(bench.session, bench.agent.org_id, agent) == Refusal.EXTERNAL
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    channel = r.json()["id"]
    r = await bench.people.alice.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@Codi bitte", "mentions": [str(agent.id)]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["agent_run"] == {
        "id": None,
        "reason": "agent.external",
        "agent_id": str(agent.id),
    }
    dm = await bench.people.alice.post("/api/dms", json={"agent_id": str(agent.id)})
    assert dm.status_code in (200, 201), dm.text
    said = await bench.people.alice.post(
        f"/api/conversations/{dm.json()['id']}/messages", json={"body_md": "Hallo"}
    )
    assert said.json()["agent_run"]["reason"] == "agent.external"
    assert await _runs(work) == 0


async def test_a_ticket_assigned_to_an_external_agent_waits_for_pick_up(work: Work) -> None:
    agent = await make_external(work)
    ticket = await work.ticket()
    assert ticket["awaiting_pickup"] is False
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}",
        json={"version": ticket["version"], "assignee": {"type": "agent", "id": str(agent.id)}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["awaiting_pickup"] is True
    assert await _runs(work) == 0
    thread = (await work.admin.get(f"/api/tickets/{ticket['number']}/thread")).json()
    messages = (await work.admin.get(f"/api/conversations/{thread['id']}/messages")).json()
    assert [m for m in messages["items"] if m["kind"] != "system"] == []  # no refusal notice
    listed = (await work.admin.get("/api/tickets", params={"space_id": str(work.space.id)})).json()
    assert [t["awaiting_pickup"] for t in listed["items"]] == [True]


async def test_no_automation_for_an_external_agent(work: Work) -> None:
    agent = await make_external(work)
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "plan"})
    body: dict[str, Any] = {
        "agent_id": str(agent.id),
        "place": {"type": "channel", "conversation_id": r.json()["id"]},
        "instruction": "Was steht an?",
        "schedule": {"kind": "recurring", "cron": "0 9 * * *", "time_zone": "Europe/Berlin"},
    }
    made = await work.admin.post("/api/automations", json=body)
    assert made.status_code == 403, made.text
    assert made.json()["error"]["code"] == "automation.not_allowed"
    assert await _runs(work) == 0
