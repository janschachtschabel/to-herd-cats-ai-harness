"""Creating a server from a catalogue entry (plan M8 task 9): the admin brings the
access and its scope; the OAuth client and shared connector it needs come with it,
through the same rules as by hand; the entry's classifications are suggestions that
only tighten, and every tool still waits for approval."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from tests.factories_catalog import CATALOG, entry, oauth_option, write_entry
from tests.factories_connectors import SHARED
from tests.factories_dms import People
from tests.factories_mcp import SERVERS, tools_of
from tests.factories_oauth import CLIENTS, connect
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub

TOKEN = "pat-SECRET-token-31"


async def install(people: People, entry_id: str, **body: Any) -> dict[str, Any]:
    response = await people.admin.post(f"{CATALOG}/{entry_id}/install", json=body)
    assert response.status_code == 201, response.text
    made: dict[str, Any] = response.json()
    return made


async def refused(people: People, entry_id: str, **body: Any) -> dict[str, Any]:
    response = await people.admin.post(f"{CATALOG}/{entry_id}/install", json=body)
    assert response.status_code in (404, 409, 422), response.text
    error: dict[str, Any] = response.json()["error"]
    return error


async def test_an_entry_suggests_and_never_approves(
    ai_people: People, mcp_egress: McpStub, catalog_dir: Path
) -> None:
    write_entry(catalog_dir, entry(mcp_egress.url))
    extra = {"name": "unknown_tool", "description": "?", "input_schema": {"type": "object"}}
    mcp_egress.state.tools.append(extra)
    made = await install(ai_people, "tracker", connector_scope="none")
    server = made["server"]
    assert server["catalog_id"] == "tracker" and server["name"] == "Tracker"
    assert server["url"] == mcp_egress.url and server["connector_scope"] == "none"
    assert made["oauth_client_id"] is None and made["connector_id"] is None
    assert server["refresh"] == {"status": "ok", "new": 3, "changed": 0, "missing": 0}
    tools = await tools_of(ai_people.admin, server["id"])
    assert {n: t["state"] for n, t in tools.items()} == dict.fromkeys(tools, "pending")
    found = {n: (t["classification"], t["suggested_classification"]) for n, t in tools.items()}
    assert found == {
        "search_issues": ("write", "write"),  # annotated read-only, suggested write: tighter
        "create_issue": ("write", "read"),  # suggested read: never looser by itself
        "unknown_tool": ("write", None),
    }
    path = f"{SERVERS}/{server['id']}/tools/{tools['create_issue']['id']}"
    body = {"classification": "read", "version": 1}
    loosen = await ai_people.admin.patch(path, json=body)
    assert loosen.json()["error"]["code"] == "mcp_tool.loosen_unconfirmed"
    confirmed = await ai_people.admin.patch(path, json={**body, "confirm_loosen": True})
    assert confirmed.json()["suggested_classification"] == "read"
    assert confirmed.json()["classification"] == "read"
    stored = (await ai_people.admin.get(f"{SERVERS}/{server['id']}")).json()
    assert stored["catalog_id"] == "tracker"


async def test_a_shared_bearer_connector_comes_with_the_server(
    ai_people: People, mcp_egress: McpStub, catalog_dir: Path, session: AsyncSession
) -> None:
    write_entry(catalog_dir, entry(mcp_egress.url))
    mcp_egress.state.require_header = ("authorization", f"Bearer {TOKEN}")
    body = {"connector_scope": "shared", "auth_kind": "bearer", "secret": {"value": TOKEN}}
    response = await ai_people.admin.post(f"{CATALOG}/tracker/install", json=body)
    assert response.status_code == 201, response.text
    made = response.json()
    assert TOKEN not in response.text
    assert made["server"]["refresh"]["status"] == "ok"
    assert made["server"]["connector_id"] == made["connector_id"] is not None
    connector = (await ai_people.admin.get(f"{SHARED}/{made['connector_id']}")).json()
    assert connector["auth_kind"] == "bearer" and connector["secret_kind"] == "enc"
    entries = (await session.scalars(select(AuditLog))).all()
    actions = {a.action for a in entries}
    assert {"connector.created", "mcp_server.created", "mcp_server.refreshed"} <= actions
    created = next(a for a in entries if a.action == "mcp_server.created")
    assert created.details["catalog_id"] == "tracker"
    assert TOKEN not in json.dumps([a.details for a in entries])


async def test_a_shared_oauth_connector_is_connected_afterwards(
    ai_people: People, oauth_ready: OAuthStub, mcp_stub: McpStub, catalog_dir: Path
) -> None:
    data = entry(mcp_stub.url, base_url={"default": oauth_ready.url}, auth=[oauth_option()])
    write_entry(catalog_dir, data)
    stub = oauth_ready.state
    made = await install(
        ai_people,
        "tracker",
        connector_scope="shared",
        auth_kind="oauth",
        client_id=stub.client_id,
        client_secret={"value": stub.client_secret},
    )
    assert made["server"]["refresh"]["status"] != "ok"  # not connected yet
    client = (await ai_people.admin.get(f"{CLIENTS}/{made['oauth_client_id']}")).json()
    assert client["authorization_endpoint"] == f"{oauth_ready.url}/authorize"
    assert client["token_endpoint"] == f"{oauth_ready.url}/token"
    assert client["revocation_endpoint"] == f"{oauth_ready.url}/revoke"
    assert client["resource"] == mcp_stub.url and client["scopes"] == "mcp read"
    assert client["token_auth"] == "client_secret_post" and client["has_client_secret"] is True
    connector = (await ai_people.admin.get(f"{SHARED}/{made['connector_id']}")).json()
    assert connector["auth_kind"] == "oauth" and connector["oauth_client_id"] == client["id"]
    assert (await connect(ai_people.admin, SHARED, made["connector_id"], oauth_ready))[
        "status"
    ] == "connected"
    refresh = await ai_people.admin.post(f"{SERVERS}/{made['server']['id']}/refresh")
    assert refresh.json()["status"] == "ok" and refresh.json()["new"] == 2
    bearer = f"Bearer {stub.issued[-1]}"
    assert any(r.headers.get("authorization") == bearer for r in mcp_stub.state.log)


async def test_personal_scopes_need_nothing_but_the_client(
    ai_people: People, mcp_egress: McpStub, catalog_dir: Path
) -> None:
    data = entry(
        mcp_egress.url,
        base_url={"default": "https://auth.example"},
        auth=[oauth_option(), {"kind": "bearer"}],
    )
    write_entry(catalog_dir, data)
    oauth = await install(
        ai_people,
        "tracker",
        connector_scope="personal",
        auth_kind="oauth",
        client_id="public-app",
        base_url="https://login.example/",
    )
    assert oauth["connector_id"] is None
    assert oauth["server"]["oauth_client_id"] == oauth["oauth_client_id"] is not None
    client = (await ai_people.admin.get(f"{CLIENTS}/{oauth['oauth_client_id']}")).json()
    assert client["token_endpoint"] == "https://login.example/token"
    assert client["has_client_secret"] is False
    fixed = await install(
        ai_people, "tracker", name="Tracker PAT", connector_scope="personal", auth_kind="bearer"
    )
    assert fixed["oauth_client_id"] is None and fixed["connector_id"] is None
    assert fixed["server"]["name"] == "Tracker PAT" and fixed["server"]["oauth_client_id"] is None
    mine = (await ai_people.alice.get("/api/ai/my-mcp-servers")).json()["items"]
    assert {s["name"] for s in mine} == {"Tracker", "Tracker PAT"}


async def test_gitlab_on_an_instance_of_ones_own(ai_people: People, mcp_egress: McpStub) -> None:
    made = await install(
        ai_people,
        "gitlab",
        connector_scope="personal",
        auth_kind="oauth",
        client_id="gitlab-app-id",
        base_url="https://git.example.com/",
    )
    server = made["server"]
    assert server["url"] == "https://git.example.com/api/v4/mcp"
    assert server["catalog_id"] == "gitlab" and server["refresh"]["status"] != "ok"
    client = (await ai_people.admin.get(f"{CLIENTS}/{made['oauth_client_id']}")).json()
    assert client["authorization_endpoint"] == "https://git.example.com/oauth/authorize"
    assert client["revocation_endpoint"] == "https://git.example.com/oauth/revoke"
    assert client["resource"] == server["url"] and client["scopes"] == "mcp"
    github = await install(ai_people, "github", connector_scope="personal", auth_kind="bearer")
    assert github["server"]["url"] == "https://api.githubcopilot.com/mcp/"


@pytest.mark.parametrize(
    ("entry_id", "body", "code", "field"),
    [
        (
            "tracker",
            {"connector_scope": "personal", "auth_kind": "bearer"},
            "install_invalid",
            "connector_scope",
        ),
        (
            "tracker",
            {"connector_scope": "shared", "auth_kind": "oauth", "client_id": "x"},
            "install_invalid",
            "auth_kind",
        ),
        (
            "tracker",
            {"connector_scope": "none", "base_url": "https://x.example"},
            "install_invalid",
            "base_url",
        ),
        (
            "gitlab",
            {"connector_scope": "personal", "auth_kind": "bearer", "base_url": "https://10.1.2.3"},
            "base_url_not_allowed",
            None,
        ),
        (
            "gitlab",
            {
                "connector_scope": "personal",
                "auth_kind": "bearer",
                "base_url": "http://git.example",
            },
            "base_url_not_allowed",
            None,
        ),
        ("gitlab", {"connector_scope": "none"}, "install_invalid", "connector_scope"),
    ],
)
async def test_an_install_the_entry_does_not_offer_is_refused(
    ai_people: People,
    mcp_egress: McpStub,
    catalog_dir: Path,
    entry_id: str,
    body: dict[str, Any],
    code: str,
    field: str | None,
) -> None:
    write_entry(catalog_dir, entry(mcp_egress.url, connector_scopes=["none", "shared"]))
    error = await refused(ai_people, entry_id, **body)
    assert error["code"] == f"mcp_catalog.{code}"
    if field is not None:
        assert error["details"]["field"] == field


@pytest.mark.parametrize(
    "body",
    [
        {"connector_scope": "shared", "auth_kind": "bearer"},  # no secret
        {"connector_scope": "personal", "auth_kind": "bearer", "secret": {"value": "x"}},
        {"connector_scope": "shared", "auth_kind": "oauth"},  # no client id
        {"connector_scope": "none", "auth_kind": "bearer"},
        {"connector_scope": "shared", "auth_kind": "bearer", "client_id": "x"},
        {"connector_scope": "none", "client_secret": {"value": "x"}},
    ],
)
async def test_an_install_is_shaped(ai_people: People, body: dict[str, Any]) -> None:
    error = await refused(ai_people, "gitlab", **body)
    assert error["code"] == "validation_failed"


async def test_a_failed_install_leaves_nothing_behind(
    ai_people: People, mcp_egress: McpStub
) -> None:
    unknown = await refused(ai_people, "nothing", connector_scope="none")
    assert unknown["code"] == "mcp_catalog.not_found"
    await install(ai_people, "gitlab", connector_scope="personal", auth_kind="bearer")
    again = await refused(
        ai_people, "gitlab", connector_scope="shared", auth_kind="oauth", client_id="abc"
    )
    assert again["code"] == "mcp_server.name_taken"
    assert (await ai_people.admin.get(CLIENTS)).json()["items"] == []
    assert (await ai_people.admin.get(SHARED)).json()["items"] == []
    servers = (await ai_people.admin.get(SERVERS)).json()["items"]
    assert [s["name"] for s in servers] == ["GitLab"]
