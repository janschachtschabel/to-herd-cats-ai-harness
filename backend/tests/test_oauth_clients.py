"""OAuth clients (plan M8 task 8): the organisation's registrations at an
authorization server (endpoints, client id, client secret, scopes, resource), set up
with `ai.manage`. A client secret goes in and never comes out."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.oauth.models import OAuthClient
from tests.factories_connectors import PERSONAL, SHARED
from tests.factories_dms import People
from tests.factories_mcp import SERVERS
from tests.factories_oauth import CLIENTS, client_body, make_oauth_client
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub


async def test_only_ai_managers_reach_oauth_clients(
    ai_people: People, oauth_stub: OAuthStub
) -> None:
    made = await make_oauth_client(ai_people.admin, oauth_stub)
    path = f"{CLIENTS}/{made['id']}"
    for who in ("alice", "gast"):
        client = getattr(ai_people, who)
        for method, url, body in (
            ("GET", CLIENTS, None),
            ("POST", CLIENTS, client_body(oauth_stub, name="X")),
            ("GET", path, None),
            ("PATCH", path, {"name": "Y", "version": 1}),
            ("DELETE", f"{path}?version=1", None),
        ):
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (method, url, response.text)
            assert response.json()["error"]["code"] == "ai.not_found"


async def test_the_client_secret_is_write_only(
    ai_people: People, oauth_stub: OAuthStub, session: AsyncSession
) -> None:
    secret = oauth_stub.state.client_secret
    assert secret is not None
    made = await make_oauth_client(ai_people.admin, oauth_stub)
    assert made["has_client_secret"] is True and made["client_secret_kind"] == "enc"
    assert made["token_auth"] == "client_secret_post"
    assert made["scopes"] == "mcp read" and made["resource"] == f"{oauth_stub.url}/mcp"
    answers = [
        (await ai_people.admin.get(CLIENTS)).text,
        (await ai_people.admin.get(f"{CLIENTS}/{made['id']}")).text,
    ]
    assert all(secret not in a for a in answers)
    row = await session.scalar(select(OAuthClient))
    assert row is not None and row.client_secret_ref is not None
    assert row.client_secret_ref.startswith("enc:") and secret not in row.client_secret_ref
    audit = (await session.scalars(select(AuditLog))).all()
    assert any(a.action == "oauth_client.created" for a in audit)
    assert all(secret not in json.dumps(a.details) for a in audit)


async def test_a_public_client_has_no_secret(ai_people: People, oauth_stub: OAuthStub) -> None:
    made = await make_oauth_client(ai_people.admin, oauth_stub, client_secret=None)
    assert made["has_client_secret"] is False and made["client_secret_kind"] is None
    env = await make_oauth_client(
        ai_people.admin, oauth_stub, name="Env", client_secret={"env": "HERD_AI_GH_SECRET"}
    )
    assert env["client_secret_kind"] == "env"


async def test_endpoints_pass_the_egress_rules(ai_people: People, oauth_stub: OAuthStub) -> None:
    for field, value in (
        ("token_endpoint", "http://oauth.example/token"),
        ("authorization_endpoint", "https://127.0.0.1/authorize"),
        ("revocation_endpoint", "https://user:pw@oauth.example/revoke"),
        ("token_endpoint", "https://oauth.example/token?x=1"),
        ("resource", "https://mcp.example/mcp#frag"),
    ):
        body = client_body(oauth_stub, **{field: value})
        response = await ai_people.admin.post(CLIENTS, json=body)
        assert response.status_code == 422, (field, response.text)
        assert response.json()["error"]["code"] == "oauth_client.url_not_allowed", field
    bad_scope = client_body(oauth_stub, scopes='repo "quoted"')
    assert (await ai_people.admin.post(CLIENTS, json=bad_scope)).status_code == 422


async def test_updates_name_the_version_and_audit_field_names(
    ai_people: People, oauth_stub: OAuthStub, session: AsyncSession
) -> None:
    made = await make_oauth_client(ai_people.admin, oauth_stub)
    path = f"{CLIENTS}/{made['id']}"
    stale = await ai_people.admin.patch(path, json={"scopes": "mcp", "version": 99})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "oauth_client.version_conflict"
    body = {"scopes": "mcp", "client_secret": {"value": "NEW-secret-9"}, "version": 1}
    updated = await ai_people.admin.patch(path, json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()["scopes"] == "mcp" and updated.json()["version"] == 2
    removed = await ai_people.admin.patch(path, json={"client_secret": None, "version": 2})
    assert removed.json()["has_client_secret"] is False
    entries = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "oauth_client.updated"))
    ).all()
    assert sorted(entries[0].details["fields"]) == ["client_secret", "scopes"]
    assert "NEW-secret-9" not in json.dumps([e.details for e in entries])


async def test_names_are_unique_and_lists_paginated(
    ai_people: People, oauth_stub: OAuthStub
) -> None:
    await make_oauth_client(ai_people.admin, oauth_stub, name="A")
    again = await ai_people.admin.post(CLIENTS, json=client_body(oauth_stub, name="a"))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "oauth_client.name_taken"
    await make_oauth_client(ai_people.admin, oauth_stub, name="B")
    first = (await ai_people.admin.get(CLIENTS, params={"limit": 1})).json()
    second = (
        await ai_people.admin.get(CLIENTS, params={"limit": 1, "cursor": first["next_cursor"]})
    ).json()
    assert {first["items"][0]["name"], second["items"][0]["name"]} == {"A", "B"}


async def test_a_client_in_use_is_not_deleted(
    ai_people: People, oauth_stub: OAuthStub, mcp_stub: McpStub
) -> None:
    for base, who in ((SHARED, "admin"), (PERSONAL, "alice")):
        made = await make_oauth_client(ai_people.admin, oauth_stub, name=f"App {who}")
        body = {"name": "Via OAuth", "auth_kind": "oauth", "oauth_client_id": made["id"]}
        connector = await getattr(ai_people, who).post(base, json=body)
        assert connector.status_code == 201, connector.text
        refused = await ai_people.admin.delete(f"{CLIENTS}/{made['id']}?version=1")
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "oauth_client.in_use"
    third = await make_oauth_client(ai_people.admin, oauth_stub, name="For a server")
    server = {
        "name": "S",
        "url": mcp_stub.url,
        "connector_scope": "personal",
        "oauth_client_id": third["id"],
    }
    assert (await ai_people.admin.post(SERVERS, json=server)).status_code == 201
    refused = await ai_people.admin.delete(f"{CLIENTS}/{third['id']}?version=1")
    assert refused.json()["error"]["code"] == "oauth_client.in_use"
    free = await make_oauth_client(ai_people.admin, oauth_stub, name="Free")
    assert (await ai_people.admin.delete(f"{CLIENTS}/{free['id']}?version=1")).status_code == 204


async def test_a_private_host_the_operator_lists_is_allowed(
    ai_people: People, oauth_stub: OAuthStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An in-house GitLab is its own authorization server (`HERD_MCP_ALLOWED_HOSTS`)."""
    body = client_body(oauth_stub, token_endpoint="https://10.1.2.3/oauth/token")
    refused = await ai_people.admin.post(CLIENTS, json=body)
    assert refused.json()["error"]["code"] == "oauth_client.url_not_allowed"
    monkeypatch.setattr(get_settings(), "mcp_allowed_hosts", "10.1.0.0/16")
    assert (await ai_people.admin.post(CLIENTS, json=body)).status_code == 201
