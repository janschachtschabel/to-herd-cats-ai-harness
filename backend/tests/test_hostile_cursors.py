"""Every list endpoint answers 422 in the error shape for any cursor it cannot use.

The list endpoints are found in the OpenAPI document (every GET with a `cursor`
parameter), so a new list endpoint is covered without being added here.
"""

import base64
import json

import pytest
from httpx import AsyncClient

from app.modules.agents.run_models import StopReason
from app.modules.groups.models import Group
from app.modules.users.models import User
from app.web.public import create_public_app
from tests.factories_agents import Bench
from tests.factories_dms import People
from tests.factories_external_agents import agent_token, make_external
from tests.factories_mcp import make_server
from tests.factories_tokens import mcp_on
from tests.factories_writing import Work
from tests.support.mcp_stub import McpStub

UUID = "0190f0f0-0000-7000-8000-000000000000"


def _b64(raw: bytes | str) -> str:
    data = raw.encode("utf-8", "surrogatepass") if isinstance(raw, str) else raw
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


HOSTILE: dict[str, str] = {
    "lone_surrogate_key": _b64(json.dumps(["a\ud800b", UUID])),
    "lone_surrogate_raw": _b64(f"2026-01-01T00:00:00+00:00\ud800|{UUID}"),
    "timestamp_overflow_high": _b64(f"9999-12-31T23:59:59-23:59|{UUID}"),
    "timestamp_overflow_low": _b64(f"0001-01-01T00:00:00+23:59|{UUID}"),
    "timestamp_naive": _b64(f"2026-01-01T00:00:00|{UUID}"),
    "key_wrong_types": _b64(json.dumps([1, 2])),
    "key_uuid_as_number": _b64(json.dumps(["a", 5])),
    "key_object": _b64(json.dumps({"a": 1, "b": 22})),
    "key_nulls": _b64(json.dumps([None, None])),
    "key_nested": _b64(json.dumps([["a"], UUID])),
    "key_with_nul": _b64(json.dumps(["a\x00", UUID])),
    "huge_integer": _b64("9" * 5000),
    "huge_float": _b64(json.dumps([1e308, UUID]).replace("1e+308", "1e999")),
    "deep_nesting": _b64("[" * 5_000),
    "truncated_base64": "QUJDRE",
    "bad_base64_length": "AAAAA",
    "not_base64": "!!!",
    "non_ascii": "äöü",
    "invalid_utf8": _b64(b"\xff\xfe\xfd|x"),
    "short_id": _b64(b"\x01\x02\x03"),
    "empty": "",
}


def _list_endpoints() -> list[str]:
    paths = create_public_app().openapi()["paths"]
    return sorted(
        path
        for path, operations in paths.items()
        if any(p["name"] == "cursor" for p in operations.get("get", {}).get("parameters", []))
    )


def test_the_list_endpoints_are_found() -> None:
    endpoints = _list_endpoints()
    assert len(endpoints) >= 11
    assert {
        "/api/channels",
        "/api/spaces/{space_id}/channels",
        "/api/conversations/{conversation_id}/messages",
        "/api/messages/{message_id}/replies",
        "/api/dms",
        "/api/conversations/unread",
        "/api/activity",
        "/api/admin/dm-inspect",
        "/api/admin/dm-inspect/{inspection_id}/messages",
        "/api/spaces/{space_id}/proposals",
        "/api/skills",
        "/api/skills/{skill_id}/versions",
        "/api/skill-proposals",
        "/api/runs",
        "/api/agents/{agent_id}/runs",
        "/api/tokens",
        "/api/ai/mcp/tokens",
        "/api/tokens/{token_id}/calls",
        "/api/ai/mcp/tokens/{token_id}/calls",
        "/api/calendar/events",
        "/api/calendar/overlays",
    } <= set(endpoints)


NEED_A_RUN = {
    "/api/runs/{run_id}/events",
    "/api/agents/{agent_id}/runs",
    "/api/agents/{agent_id}/spaces",
    "/api/agents/{agent_id}/automations",
    "/api/automations/{automation_id}/firings",
    "/api/ai/my-connectors",  # needs `ai.use`
    "/api/ai/my-mcp-servers",  # needs `ai.use`
}

SERVER_TOOLS = "/api/ai/mcp-servers/{server_id}/tools"

# Lists that need more than a cursor (besides the DM inspection's person).
EXTRA: dict[str, dict[str, str]] = {
    "/api/calendar/events": {"from": "2026-11-23T00:00:00Z", "to": "2026-11-24T00:00:00Z"},
    "/api/calendar/overlays": {"from": "2026-11-23", "to": "2026-11-24"},
}

AGENT_TOKENS = {
    "/api/agents/{agent_id}/tokens",
    "/api/agents/{agent_id}/tokens/{token_id}/calls",
}


@pytest.mark.parametrize("name", sorted(HOSTILE))
async def test_hostile_cursors_answer_422_everywhere(
    name: str, owner: AsyncClient, group: Group, member: User
) -> None:
    space_id = (await owner.post("/api/spaces", json={"kind": "team", "name": "T"})).json()["id"]
    mcp = {"enabled": True, "data_location": "external", "version": 1}
    assert (await owner.put("/api/ai/mcp", json=mcp)).status_code == 200  # `/api/tokens`
    page = await owner.post(f"/api/spaces/{space_id}/pages", json={"title": "Seite"})
    channel = await owner.post(f"/api/spaces/{space_id}/channels", json={"name": "k"})
    message = await owner.post(
        f"/api/conversations/{channel.json()['id']}/messages", json={"body_md": "m"}
    )
    dm = await owner.post("/api/dms", json={"user_ids": [str(member.id)]})
    inspection = await owner.post(
        "/api/admin/dm-inspect",
        json={"conversation_id": dm.json()["id"], "reason": "hostile cursor test"},
    )
    ticket = await owner.post(f"/api/spaces/{space_id}/tickets", json={"title": "Ticket"})
    skill = await owner.post("/api/skills", json={"name": "s", "description": "d", "content": "c"})
    token = await owner.post(
        "/api/tokens", json={"name": "t", "mode": "read", "expires_in_days": 1}
    )
    calendar = await owner.post(f"/api/spaces/{space_id}/calendars", json={"name": "K"})
    event = await owner.post(
        f"/api/calendars/{calendar.json()['id']}/events",
        json={"title": "T", "starts_at": "2026-11-23T10:00:00Z", "ends_at": "2026-11-23T11:00:00Z"},
    )
    ids = {
        "{event_id}": event.json()["id"],
        "{number}": str(ticket.json()["number"]),
        "{category}": "open",
        "{status_id}": ticket.json()["status"]["id"],
        "{inspection_id}": inspection.json()["id"],
        "{space_id}": space_id,
        "{group_id}": str(group.id),
        "{page_id}": page.json()["id"],
        "{conversation_id}": channel.json()["id"],
        "{message_id}": message.json()["id"],
        "{skill_id}": skill.json()["id"],
        "{token_id}": token.json()["id"],
        "{user_id}": str(member.id),
    }
    for template in _list_endpoints():
        if template in NEED_A_RUN:
            continue  # test_hostile_cursors_on_a_runs_events
        if template == SERVER_TOOLS:
            continue  # test_hostile_cursors_on_a_servers_tools
        if template in AGENT_TOKENS:
            continue  # test_hostile_cursors_on_an_agents_tokens
        path = template
        for placeholder, value in ids.items():
            path = path.replace(placeholder, value)
        assert "{" not in path, f"no id for {path}: add one above"
        # Lists that need more than a cursor.
        extra = EXTRA.get(template, {})
        if template == "/api/admin/dm-inspect":
            extra = {"user_id": str(member.id)}
        response = await owner.get(path, params={"cursor": HOSTILE[name], **extra})
        if name == "empty":
            # An empty cursor means "first page".
            assert response.status_code == 200, (path, response.text)
            continue
        assert response.status_code == 422, (path, response.text)
        error = response.json()["error"]
        assert error["code"] == "validation_failed" and len(error["trace_id"]) == 32


async def test_hostile_cursors_on_a_runs_events(bench: Bench) -> None:
    """The lists that need a run (an agent, a connection, a DM), an automation or
    `ai.use`."""
    posted = await bench.say("Hi")
    assert await bench.run_next() == StopReason.COMPLETED
    run_id = posted["agent_run"]["id"]
    daily = {"kind": "recurring", "cron": "0 9 * * *", "time_zone": "UTC"}
    automation = await bench.people.admin.post(
        "/api/automations",
        json={
            "agent_id": str(bench.agent.id),
            "place": {"type": "dm"},
            "instruction": "x",
            "schedule": daily,
        },
    )
    assert automation.status_code == 201, automation.text
    ids = {
        "{run_id}": run_id,
        "{agent_id}": str(bench.agent.id),
        "{automation_id}": automation.json()["id"],
    }
    for template in NEED_A_RUN:
        path = template
        for placeholder, value in ids.items():
            path = path.replace(placeholder, value)
        for name, cursor in HOSTILE.items():
            response = await bench.people.admin.get(path, params={"cursor": cursor})
            if name == "empty":
                assert response.status_code == 200, (name, response.text)
                continue
            assert response.status_code == 422, (name, response.text)
            assert response.json()["error"]["code"] == "validation_failed"


async def test_hostile_cursors_on_an_agents_tokens(work: Work) -> None:
    """The token lists of an external agent (plan M8 task 4)."""
    await mcp_on(work.admin)
    agent = await make_external(work)
    token = await agent_token(work.admin, agent)
    for template in AGENT_TOKENS:
        path = template.replace("{agent_id}", str(agent.id)).replace("{token_id}", token["id"])
        for name, cursor in HOSTILE.items():
            response = await work.admin.get(path, params={"cursor": cursor})
            if name == "empty":
                assert response.status_code == 200, (path, response.text)
                continue
            assert response.status_code == 422, (path, name, response.text)
            assert response.json()["error"]["code"] == "validation_failed"


async def test_hostile_cursors_on_a_servers_tools(ai_people: People, mcp_egress: McpStub) -> None:
    """The tool list of an external MCP server (one is read from the MCP stub)."""
    server = await make_server(ai_people.admin, mcp_egress)
    path = SERVER_TOOLS.replace("{server_id}", server["id"])
    for name, cursor in HOSTILE.items():
        response = await ai_people.admin.get(path, params={"cursor": cursor})
        if name == "empty":
            assert response.status_code == 200, (name, response.text)
            continue
        assert response.status_code == 422, (name, response.text)
        assert response.json()["error"]["code"] == "validation_failed"
