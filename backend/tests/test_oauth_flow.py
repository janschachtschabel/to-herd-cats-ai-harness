"""Connecting an OAuth connector (plan M8 task 8): authorization code with PKCE (S256);
`state` and the verifier in Postgres, bound to the login session, used once; the
redirect URI derived from the configured public address, never from the request;
tokens stored only as `enc:` secrets; disconnecting revokes at the provider."""

import uuid
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.config import get_settings
from app.core.models_base import utcnow
from app.modules.audit.models import AuditLog
from app.modules.connectors.models import Connector
from app.modules.oauth.models import OAuthFlow
from tests.factories_connectors import PERSONAL, SHARED, make_connector
from tests.factories_dms import People
from tests.factories_oauth import (
    LEGACY_CALLBACK,
    PUBLIC_URL,
    authorize,
    callback_for,
    connect,
    make_oauth_client,
    query_of,
)
from tests.support.oauth_stub import OAuthStub


def _redirect_uri(connector: dict[str, Any], base: str = PUBLIC_URL) -> str:
    """The callback of the connector's OAuth app (J13)."""
    return f"{base}/api/ai/oauth/{connector['oauth_client_id']}/callback"


async def _oauth_connector(
    people: People, stub: OAuthStub, base: str = SHARED, who: str = "admin", **client: Any
) -> dict[str, Any]:
    made = await make_oauth_client(people.admin, stub, name=f"App {who} {base}", **client)
    body = {"name": "Stub", "auth_kind": "oauth", "oauth_client_id": made["id"]}
    response = await getattr(people, who).post(base, json=body)
    assert response.status_code == 201, response.text
    connector: dict[str, Any] = response.json()
    assert connector["has_secret"] is False and connector["secret_kind"] is None
    assert connector["oauth_client_id"] == made["id"]
    return connector


async def _row(session: AsyncSession, connector_id: object) -> Connector:
    row = await session.scalar(
        select(Connector)
        .where(Connector.id == connector_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def test_the_authorization_request_carries_pkce_state_scope_and_resource(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == f"{oauth_ready.url}/authorize"
    query = dict(parse_qsl(parts.query))
    assert query["response_type"] == "code"
    assert query["client_id"] == oauth_ready.state.client_id
    assert query["redirect_uri"] == _redirect_uri(connector)
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) == 43
    assert len(query["state"]) >= 43
    assert query["scope"] == "mcp read" and query["resource"] == f"{oauth_ready.url}/mcp"
    assert "client_secret" not in url and oauth_ready.state.client_secret not in url


async def test_a_shared_connector_is_connected_and_tokens_stored_encrypted(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    result = await connect(ai_people.admin, SHARED, connector["id"], oauth_ready)
    assert result == {"status": "connected", "connector": connector["id"], "scope": "shared"}
    shown = (await ai_people.admin.get(f"{SHARED}/{connector['id']}")).json()
    assert shown["has_secret"] is True and shown["secret_kind"] == "enc"
    assert shown["version"] == connector["version"] + 1
    row = await _row(session, connector["id"])
    assert row.secret_ref is not None and row.refresh_token_ref is not None
    assert row.secret_ref.startswith("enc:") and row.refresh_token_ref.startswith("enc:")
    access, refresh = oauth_ready.state.issued[-1], f"rt-{oauth_ready.state.issued[-1][3:]}"
    assert secrets.resolve(row.secret_ref).get_secret_value() == access
    assert secrets.resolve(row.refresh_token_ref).get_secret_value() == refresh
    assert access not in row.secret_ref and refresh not in row.refresh_token_ref
    assert row.token_expires_at is not None
    assert timedelta(minutes=55) < row.token_expires_at - utcnow() <= timedelta(hours=1)
    (exchange,) = oauth_ready.state.token_requests("authorization_code")
    assert exchange.form["redirect_uri"] == _redirect_uri(connector)
    assert exchange.form["resource"] == f"{oauth_ready.url}/mcp"
    assert len(exchange.form["code_verifier"]) >= 43
    assert exchange.form["client_secret"] == oauth_ready.state.client_secret
    assert exchange.headers["accept"] == "application/json"
    assert await session.scalar(select(OAuthFlow)) is None
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "connector.connected"))
    assert audit is not None and audit.details == {"scope": "shared", "refresh_token": True}


async def test_basic_client_authentication_and_public_clients(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    oauth_ready.state.token_auth = "client_secret_basic"
    basic = await _oauth_connector(ai_people, oauth_ready, token_auth="client_secret_basic")
    assert (await connect(ai_people.admin, SHARED, basic["id"], oauth_ready))[
        "status"
    ] == "connected"
    assert "client_secret" not in oauth_ready.state.log[-1].form
    oauth_ready.state.token_auth = "none"
    public = await _oauth_connector(ai_people, oauth_ready, PERSONAL, "alice", client_secret=None)
    assert (await connect(ai_people.alice, PERSONAL, public["id"], oauth_ready))[
        "status"
    ] == "connected"


async def test_state_is_used_once(oauth_ready: OAuthStub, ai_people: People) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    query = oauth_ready.state.authorize(url)
    first = await ai_people.admin.get(callback_for(url), params=query)
    assert query_of(first.headers["location"])["status"] == "connected"
    again = await ai_people.admin.get(callback_for(url), params=query)
    assert again.status_code == 303
    assert query_of(again.headers["location"]) == {"status": "invalid"}
    assert len(oauth_ready.state.token_requests("authorization_code")) == 1


async def test_state_is_bound_to_the_login_session(
    oauth_ready: OAuthStub, ai_people: People, make_client: Any, client: Any
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready, PERSONAL, "alice")
    url = await authorize(ai_people.alice, PERSONAL, connector["id"])
    query = oauth_ready.state.authorize(url)
    for other in (ai_people.bob, ai_people.admin, client):
        response = await other.get(callback_for(url), params=query)
        assert response.status_code == 303
        assert query_of(response.headers["location"]) == {"status": "invalid"}
    assert oauth_ready.state.token_requests("authorization_code") == []
    done = await ai_people.alice.get(callback_for(url), params=query)
    assert query_of(done.headers["location"])["status"] == "connected"


async def test_unknown_and_expired_state_and_a_refusal(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    for path in (LEGACY_CALLBACK, _redirect_uri(connector, "")):
        unknown = await ai_people.admin.get(path, params={"state": "x" * 43, "code": "c"})
        assert query_of(unknown.headers["location"]) == {"status": "invalid"}
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    query = oauth_ready.state.authorize(url)
    await session.execute(update(OAuthFlow).values(expires_at=utcnow() - timedelta(seconds=1)))
    expired = await ai_people.admin.get(callback_for(url), params=query)
    assert query_of(expired.headers["location"]) == {"status": "invalid"}
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    state = dict(parse_qsl(urlsplit(url).query))["state"]
    denied = await ai_people.admin.get(
        callback_for(url),
        params={"state": state, "error": "access_denied", "error_description": "no"},
    )
    assert query_of(denied.headers["location"])["status"] == "denied"
    assert oauth_ready.state.token_requests("authorization_code") == []
    assert await session.scalar(select(OAuthFlow)) is None


async def test_a_failed_exchange_leaves_the_connector_unconnected(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    oauth_ready.state.failures.append(500)
    result = await connect(ai_people.admin, SHARED, connector["id"], oauth_ready)
    assert result == {"status": "failed", "connector": connector["id"], "scope": "shared"}
    shown = (await ai_people.admin.get(f"{SHARED}/{connector['id']}")).json()
    assert shown["has_secret"] is False


async def test_a_deleted_connector_ends_its_flow(oauth_ready: OAuthStub, ai_people: People) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    query = oauth_ready.state.authorize(url)
    await ai_people.admin.delete(f"{SHARED}/{connector['id']}?version=1")
    gone = await ai_people.admin.get(callback_for(url), params=query)
    assert query_of(gone.headers["location"]) == {"status": "invalid"}


async def test_only_the_owner_connects_a_personal_connector(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready, PERSONAL, "alice")
    for who in ("admin", "bob"):
        response = await getattr(ai_people, who).post(f"{PERSONAL}/{connector['id']}/authorize")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "connector.not_found"
    shared_path = await ai_people.alice.post(f"{SHARED}/{connector['id']}/authorize")
    assert shared_path.json()["error"]["code"] == "ai.not_found"
    result = await connect(ai_people.alice, PERSONAL, connector["id"], oauth_ready)
    assert result["status"] == "connected" and result["scope"] == "personal"


async def test_authorize_needs_an_oauth_connector_and_a_public_address(
    oauth_ready: OAuthStub, ai_people: People, monkeypatch: pytest.MonkeyPatch
) -> None:
    bearer = await make_connector(ai_people.admin)
    refused = await ai_people.admin.post(f"{SHARED}/{bearer['id']}/authorize")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "connector.not_oauth"
    connector = await _oauth_connector(ai_people, oauth_ready)
    for address in (None, "http://herd.example"):
        monkeypatch.setattr(get_settings(), "public_url", address)
        response = await ai_people.admin.post(f"{SHARED}/{connector['id']}/authorize")
        assert response.status_code == 422, address
        assert response.json()["error"]["code"] == "connector.oauth_unconfigured"
    monkeypatch.setattr(get_settings(), "public_url", "http://localhost:5173")
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    assert dict(parse_qsl(urlsplit(url).query))["redirect_uri"] == (
        _redirect_uri(connector, "http://localhost:5173")
    )


async def test_the_redirect_uri_ignores_the_request_headers(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    response = await ai_people.admin.post(
        f"{SHARED}/{connector['id']}/authorize",
        headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example", "Origin": "x"},
    )
    query = dict(parse_qsl(urlsplit(response.json()["authorization_url"]).query))
    assert query["redirect_uri"] == _redirect_uri(connector)


async def test_oauth_connectors_take_no_secret_and_keep_their_kind(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    made = await make_oauth_client(ai_people.admin, oauth_ready)
    body = {
        "name": "X",
        "auth_kind": "oauth",
        "oauth_client_id": made["id"],
        "secret": {"value": "nope"},
    }
    assert (await ai_people.admin.post(SHARED, json=body)).status_code == 422
    no_client = {"name": "Y", "auth_kind": "oauth"}
    assert (await ai_people.admin.post(SHARED, json=no_client)).status_code == 422
    unknown = {"name": "Z", "auth_kind": "oauth", "oauth_client_id": str(uuid.uuid4())}
    response = await ai_people.alice.post(PERSONAL, json=unknown)
    assert response.json()["error"]["code"] == "connector.oauth_client_invalid"
    connector = await _oauth_connector(ai_people, oauth_ready)
    path = f"{SHARED}/{connector['id']}"
    for change in ({"auth_kind": "bearer"}, {"secret": {"value": "x"}}):
        response = await ai_people.admin.patch(path, json={**change, "version": 1})
        assert response.status_code == 422, change
    bearer = await make_connector(ai_people.admin, name="Plain")
    to_oauth = await ai_people.admin.patch(
        f"{SHARED}/{bearer['id']}", json={"auth_kind": "oauth", "version": 1}
    )
    assert to_oauth.status_code == 422


async def test_disconnect_revokes_at_the_provider_and_forgets_the_tokens(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready, PERSONAL, "alice")
    await connect(ai_people.alice, PERSONAL, connector["id"], oauth_ready)
    access = oauth_ready.state.issued[-1]
    path = f"{PERSONAL}/{connector['id']}"
    stale = await ai_people.alice.post(f"{path}/disconnect", json={"version": 1})
    assert stale.status_code == 409
    done = await ai_people.alice.post(f"{path}/disconnect", json={"version": 2})
    assert done.status_code == 200, done.text
    assert done.json()["has_secret"] is False and done.json()["version"] == 3
    row = await _row(session, connector["id"])
    assert row.secret_ref is None and row.refresh_token_ref is None
    assert row.token_expires_at is None
    assert oauth_ready.state.revoked == [f"rt-{access[3:]}", access]
    revocations = [r for r in oauth_ready.state.log if r.path == "/revoke"]
    assert [r.form["token_type_hint"] for r in revocations] == ["refresh_token", "access_token"]
    audit = await session.scalar(
        select(AuditLog).where(AuditLog.action == "connector.disconnected")
    )
    assert audit is not None and audit.details == {"scope": "personal"}


async def test_deleting_a_connected_connector_revokes_too(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready)
    await connect(ai_people.admin, SHARED, connector["id"], oauth_ready)
    access = oauth_ready.state.issued[-1]
    deleted = await ai_people.admin.delete(f"{SHARED}/{connector['id']}?version=2")
    assert deleted.status_code == 204
    assert access in oauth_ready.state.revoked


async def test_without_a_revocation_endpoint_disconnect_only_forgets(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    connector = await _oauth_connector(ai_people, oauth_ready, revocation_endpoint=None)
    await connect(ai_people.admin, SHARED, connector["id"], oauth_ready)
    done = await ai_people.admin.post(f"{SHARED}/{connector['id']}/disconnect", json={"version": 2})
    assert done.json()["has_secret"] is False
    assert oauth_ready.state.revoked == []
