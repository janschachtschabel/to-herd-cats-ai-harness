"""External MCP servers (plan M8 decision 7, task 6): managed with `ai.manage`, only
Streamable HTTP over https through the egress guard; the tool list is read when a
server is created; a shared connector a server uses is not deleted."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress
from app.core.actor import Actor
from app.core.egress import Network
from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import AuditLog
from app.modules.mcp_servers.service import ServerService
from app.modules.orgs.models import Organization
from tests.factories import MakeUser
from tests.factories_connectors import SHARED, make_connector
from tests.factories_dms import People
from tests.factories_mcp import SERVERS, make_server, tools_of
from tests.support.mcp_stub import McpStub


async def test_creating_a_server_reads_its_tools(ai_people: People, mcp_egress: McpStub) -> None:
    made = await make_server(ai_people.admin, mcp_egress)
    assert made["url"] == mcp_egress.url and made["enabled"] is True
    assert made["data_location"] == "external" and made["connector_scope"] == "none"
    assert made["connector_id"] is None and made["version"] == 1
    assert made["refresh"] == {"status": "ok", "new": 2, "changed": 0, "missing": 0}
    tools = await tools_of(ai_people.admin, made["id"])
    assert set(tools) == {"search_issues", "create_issue"}
    assert all(t["state"] == "pending" for t in tools.values())


async def test_a_server_the_guard_refuses_is_kept_without_tools(
    ai_people: People, mcp_stub: McpStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The name resolves to a private address: the server is saved, the reading fails
    with a state, and nothing reached the stub."""

    async def private(host: str, port: int) -> list[str]:
        return ["10.0.0.5"]

    monkeypatch.setattr(egress, "_network", Network(resolver=private))
    made = await make_server(ai_people.admin, mcp_stub)
    assert made["refresh"]["status"] == "blocked"
    assert await tools_of(ai_people.admin, made["id"]) == {}
    assert mcp_stub.state.log == []


async def test_only_https_urls_without_secrets_or_private_addresses(
    ai_people: People, mcp_egress: McpStub
) -> None:
    for url in (
        "http://mcp.example.com/mcp",
        "https://127.0.0.1/mcp",
        "https://10.0.0.8/mcp",
        "https://169.254.169.254/mcp",
        "https://localhost/mcp",
        "https://user:pw@mcp.example.com/mcp",
        "https://mcp.example.com/mcp?token=x",
        "stdio:///usr/bin/server",
        "file:///etc/passwd",
    ):
        response = await ai_people.admin.post(SERVERS, json={"name": "X", "url": url})
        assert response.status_code == 422, (url, response.text)
        assert response.json()["error"]["code"] in (
            "mcp_server.url_not_allowed",
            "validation_failed",
        )
    assert mcp_egress.state.log == []


async def test_only_ai_managers_reach_servers(ai_people: People, mcp_egress: McpStub) -> None:
    made = await make_server(ai_people.admin, mcp_egress)
    path = f"{SERVERS}/{made['id']}"
    for client in (ai_people.alice, ai_people.gast):
        for method, url, body in (
            ("GET", SERVERS, None),
            ("POST", SERVERS, {"name": "X", "url": mcp_egress.url}),
            ("GET", path, None),
            ("PATCH", path, {"name": "Y", "version": 1}),
            ("DELETE", f"{path}?version=1", None),
            ("POST", f"{path}/refresh", {}),
            ("POST", f"{path}/test", {}),
            ("GET", f"{path}/tools", None),
        ):
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (method, url, response.text)
            assert response.json()["error"]["code"] == "ai.not_found"


async def test_writes_name_the_version_and_are_audited(
    ai_people: People, mcp_egress: McpStub, session: AsyncSession
) -> None:
    made = await make_server(ai_people.admin, mcp_egress)
    path = f"{SERVERS}/{made['id']}"
    changed = await ai_people.admin.patch(
        path, json={"name": "Neu", "enabled": False, "data_location": "eu", "version": 1}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["enabled"] is False and changed.json()["data_location"] == "eu"
    stale = await ai_people.admin.patch(path, json={"name": "Alt", "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "mcp_server.version_conflict"
    assert (await ai_people.admin.delete(f"{path}?version=1")).status_code == 409
    assert (await ai_people.admin.delete(f"{path}?version=2")).status_code == 204
    assert (await ai_people.admin.get(path)).status_code == 404
    actions = [
        a.action
        for a in (
            await session.scalars(
                select(AuditLog).where(AuditLog.target_id == made["id"]).order_by(AuditLog.id)
            )
        ).all()
    ]
    assert actions == [
        "mcp_server.created",
        "mcp_server.refreshed",
        "mcp_server.updated",
        "mcp_server.deleted",
    ]


async def test_names_are_unique(ai_people: People, mcp_egress: McpStub) -> None:
    await make_server(ai_people.admin, mcp_egress)
    taken = await ai_people.admin.post(SERVERS, json={"name": "tracker", "url": mcp_egress.url})
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "mcp_server.name_taken"


async def test_a_shared_connector_is_named_and_kept_while_in_use(
    ai_people: People, mcp_egress: McpStub
) -> None:
    connector = await make_connector(ai_people.admin)
    missing = await ai_people.admin.post(
        SERVERS, json={"name": "X", "url": mcp_egress.url, "connector_scope": "shared"}
    )
    assert missing.status_code == 422
    made = await make_server(
        ai_people.admin, mcp_egress, connector_scope="shared", connector_id=connector["id"]
    )
    assert made["connector_id"] == connector["id"]
    in_use = await ai_people.admin.delete(f"{SHARED}/{connector['id']}?version=1")
    assert in_use.status_code == 409
    assert in_use.json()["error"]["code"] == "connector.in_use"
    released = await ai_people.admin.patch(
        f"{SERVERS}/{made['id']}", json={"connector_scope": "none", "version": 1}
    )
    assert released.status_code == 200 and released.json()["connector_id"] is None
    assert (
        await ai_people.admin.delete(f"{SHARED}/{connector['id']}?version=1")
    ).status_code == 204


async def test_a_personal_connector_cannot_serve_as_shared(
    ai_people: People, mcp_egress: McpStub
) -> None:
    personal = await make_connector(ai_people.admin, "/api/ai/my-connectors")
    response = await ai_people.admin.post(
        SERVERS,
        json={
            "name": "X",
            "url": mcp_egress.url,
            "connector_scope": "shared",
            "connector_id": personal["id"],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mcp_server.connector_invalid"


async def test_test_connection_reports_a_state_and_changes_nothing(
    ai_people: People, mcp_egress: McpStub
) -> None:
    made = await make_server(ai_people.admin, mcp_egress)
    mcp_egress.state.tools.append({"name": "later", "description": "d"})
    tested = await ai_people.admin.post(f"{SERVERS}/{made['id']}/test", json={})
    assert tested.status_code == 200, tested.text
    body = tested.json()
    assert body["status"] == "ok" and body["tools"] == 3 and body["duration_ms"] >= 0
    assert "later" not in await tools_of(ai_people.admin, made["id"])
    mcp_egress.state.failures.extend([401] * 3)
    refused = await ai_people.admin.post(f"{SERVERS}/{made['id']}/test", json={})
    assert refused.json()["status"] == "unauthorized"


async def test_lists_are_paginated(ai_people: People, mcp_egress: McpStub) -> None:
    for n in range(3):
        await make_server(ai_people.admin, mcp_egress, name=f"S{n}")
    first = (await ai_people.admin.get(SERVERS, params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = (
        await ai_people.admin.get(SERVERS, params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [s["name"] for s in rest["items"]] == ["S2"]
    assert "refresh" not in json.dumps(rest)


async def test_other_organisations_see_nothing(
    ai_people: People, mcp_egress: McpStub, session: AsyncSession, make_user: MakeUser
) -> None:
    made = await make_server(ai_people.admin, mcp_egress)
    other = Organization(name="Other")
    session.add(other)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other)
    actor = Actor(other.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    service = ServerService(session)
    assert (await service.list(actor, PageParams())).items == []
    try:
        await service.get(actor, made["id"])
    except NotFound as missing:
        assert missing.code == "mcp_server.not_found"
    else:
        raise AssertionError("another organisation's server was found")


async def test_an_unusable_connector_secret_is_a_state(
    ai_people: People, mcp_egress: McpStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERD_AI_UNSET_MCP_TOKEN", raising=False)
    connector = await make_connector(ai_people.admin, secret={"env": "HERD_AI_UNSET_MCP_TOKEN"})
    made = await make_server(
        ai_people.admin, mcp_egress, connector_scope="shared", connector_id=connector["id"]
    )
    assert made["refresh"]["status"] == "secret_unavailable"
    assert mcp_egress.state.log == []
