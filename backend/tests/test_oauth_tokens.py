"""Using an OAuth connector (plan M8 task 8): the access token goes on the call; it is
renewed shortly before it expires and once after a 401, with the refresh token, in a
transaction of its own that locks the connector, so two workers never refresh at
once; a refresh token the provider no longer takes disconnects the connector."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.models_base import utcnow
from app.modules.connectors.models import Connector
from app.modules.mcp_servers.calls import ToolCaller
from app.modules.mcp_servers.errors import CredentialUnavailable, NotConnected
from app.modules.oauth import tokens
from tests.factories_connectors import PERSONAL, SHARED
from tests.factories_dms import People
from tests.factories_mcp import SERVERS, approve, make_server, tools_of
from tests.factories_oauth import connect, make_oauth_client
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub


async def _connected(people: People, stub: OAuthStub, base: str, who: str) -> dict[str, Any]:
    made = await make_oauth_client(people.admin, stub, name=f"App {who}")
    body = {"name": "Stub", "auth_kind": "oauth", "oauth_client_id": made["id"]}
    connector = (await getattr(people, who).post(base, json=body)).json()
    assert (await connect(getattr(people, who), base, connector["id"], stub))[
        "status"
    ] == "connected"
    result: dict[str, Any] = connector
    return result


async def _shared_server(people: People, oauth: OAuthStub, mcp: McpStub) -> dict[str, Any]:
    connector = await _connected(people, oauth, SHARED, "admin")
    server = await make_server(
        people.admin, mcp, connector_scope="shared", connector_id=connector["id"]
    )
    tools = await tools_of(people.admin, server["id"])
    await approve(people.admin, server["id"], tools["search_issues"])
    return {"server": server, "connector": connector}


async def _call(session: AsyncSession, people: People, server_id: object, who: str = "alice"):  # type: ignore[no-untyped-def]
    user = people.users[who]
    return await ToolCaller(session).call_tool(
        user.org_id, server_id, "search_issues", {"q": "x"}, on_behalf_of=user.id
    )


def _bearers(mcp: McpStub) -> list[str]:
    return [r.headers.get("authorization", "") for r in mcp.state.log]


async def _expire_soon(session: AsyncSession, connector_id: object) -> None:
    await session.execute(
        update(Connector)
        .where(Connector.id == connector_id)
        .values(token_expires_at=utcnow() + timedelta(seconds=10))
    )


async def _row(session: AsyncSession, connector_id: object) -> Connector:
    row = await session.scalar(
        select(Connector)
        .where(Connector.id == connector_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def test_the_access_token_goes_on_the_call(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    access = oauth_ready.state.issued[-1]
    mcp_stub.state.log.clear()
    result = await _call(session, ai_people, made["server"]["id"])
    assert result.is_error is False
    assert set(_bearers(mcp_stub)) == {f"Bearer {access}"}
    assert oauth_ready.state.token_requests("refresh_token") == []


async def test_a_token_about_to_expire_is_renewed_first(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    old_refresh = f"rt-{oauth_ready.state.issued[-1][3:]}"
    await _expire_soon(session, made["connector"]["id"])
    mcp_stub.state.log.clear()
    await _call(session, ai_people, made["server"]["id"])
    (renewal,) = oauth_ready.state.token_requests("refresh_token")
    assert renewal.form["refresh_token"] == old_refresh
    assert renewal.form["resource"] == f"{oauth_ready.url}/mcp"
    new_access = oauth_ready.state.issued[-1]
    assert set(_bearers(mcp_stub)) == {f"Bearer {new_access}"}
    row = await _row(session, made["connector"]["id"])
    assert row.secret_ref is not None and row.refresh_token_ref is not None
    assert secrets.resolve(row.secret_ref).get_secret_value() == new_access
    assert secrets.resolve(row.refresh_token_ref).get_secret_value() == f"rt-{new_access[3:]}"
    assert row.token_expires_at is not None and row.token_expires_at > utcnow() + timedelta(
        minutes=50
    )


async def test_a_401_renews_once_and_calls_again(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    current = int(oauth_ready.state.issued[-1][3:])
    mcp_stub.state.require_header = ("authorization", f"Bearer at-{current + 1}")
    result = await _call(session, ai_people, made["server"]["id"])
    assert result.is_error is False
    assert len(oauth_ready.state.token_requests("refresh_token")) == 1
    assert mcp_stub.state.calls == [("search_issues", {"q": "x"})]


async def test_a_second_401_is_the_servers_answer(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    from app.modules.mcp_servers.errors import RemoteFailed

    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    mcp_stub.state.require_header = ("authorization", "Bearer never")
    with pytest.raises(RemoteFailed) as caught:
        await _call(session, ai_people, made["server"]["id"])
    assert caught.value.status == "unauthorized"
    assert len(oauth_ready.state.token_requests("refresh_token")) == 1


async def test_a_refused_refresh_token_disconnects(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    oauth_ready.state.refresh.clear()  # the provider forgot the grant
    await _expire_soon(session, made["connector"]["id"])
    with pytest.raises(NotConnected):
        await _call(session, ai_people, made["server"]["id"])
    row = await _row(session, made["connector"]["id"])
    assert row.secret_ref is None and row.refresh_token_ref is None
    shown = (await ai_people.admin.get(f"{SHARED}/{made['connector']['id']}")).json()
    assert shown["has_secret"] is False


async def test_a_provider_outage_keeps_the_tokens(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    oauth_ready.state.failures.append(503)
    await _expire_soon(session, made["connector"]["id"])
    with pytest.raises(CredentialUnavailable):
        await _call(session, ai_people, made["server"]["id"])
    row = await _row(session, made["connector"]["id"])
    assert row.secret_ref is not None and row.refresh_token_ref is not None


async def test_a_provider_that_keeps_its_refresh_token(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    oauth_ready.state.rotate = False
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    first_refresh = f"rt-{oauth_ready.state.issued[-1][3:]}"
    for _ in range(2):
        await _expire_soon(session, made["connector"]["id"])
        await _call(session, ai_people, made["server"]["id"])
    renewals = oauth_ready.state.token_requests("refresh_token")
    assert [r.form["refresh_token"] for r in renewals] == [first_refresh, first_refresh]


async def test_a_personal_server_uses_each_persons_own_token(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    app = await make_oauth_client(ai_people.admin, oauth_ready, name="Per person")
    server = await make_server(
        ai_people.admin, mcp_stub, connector_scope="personal", oauth_client_id=app["id"]
    )
    assert server["oauth_client_id"] == app["id"]
    tools = await tools_of(ai_people.admin, server["id"])
    await approve(ai_people.admin, server["id"], tools["search_issues"])
    mine = (await ai_people.alice.get("/api/ai/my-mcp-servers")).json()["items"]
    assert mine == [
        {
            "id": server["id"],
            "name": server["name"],
            "connected": False,
            "oauth_client_id": app["id"],
        }
    ]
    body = {
        "name": "Mine",
        "auth_kind": "oauth",
        "oauth_client_id": app["id"],
        "mcp_server_id": server["id"],
    }
    connector = (await ai_people.alice.post(PERSONAL, json=body)).json()
    with pytest.raises(NotConnected):  # created, not yet connected
        await _call(session, ai_people, server["id"])
    await connect(ai_people.alice, PERSONAL, connector["id"], oauth_ready)
    alices = oauth_ready.state.issued[-1]
    mcp_stub.state.log.clear()
    await _call(session, ai_people, server["id"])
    assert set(_bearers(mcp_stub)) == {f"Bearer {alices}"}
    with pytest.raises(NotConnected):
        await _call(session, ai_people, server["id"], who="bob")


async def test_oauth_client_only_for_personal_servers(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub
) -> None:
    app = await make_oauth_client(ai_people.admin, oauth_ready)
    body = {"name": "S", "url": mcp_stub.url, "oauth_client_id": app["id"]}
    response = await ai_people.admin.post(SERVERS, json=body)
    assert response.status_code == 422
    unknown = {**body, "connector_scope": "personal", "oauth_client_id": server_id_like(app)}
    response = await ai_people.admin.post(SERVERS, json=unknown)
    assert response.json()["error"]["code"] == "mcp_server.oauth_client_invalid"


def server_id_like(made: dict[str, Any]) -> str:
    import uuid

    return str(uuid.UUID(int=uuid.UUID(made["id"]).int ^ 1))


async def test_renew_in_its_own_unit_tells_a_used_token_from_a_new_one(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    connector = await _connected(ai_people, oauth_ready, SHARED, "admin")
    org_id = ai_people.users["admin"].org_id
    old = oauth_ready.state.issued[-1]
    renewed = await tokens.renew(org_id, connector["id"], used=old)
    assert renewed == {"Authorization": f"Bearer {oauth_ready.state.issued[-1]}"}
    again = await tokens.renew(org_id, connector["id"], used=old)  # someone renewed already
    assert again == renewed
    assert len(oauth_ready.state.token_requests("refresh_token")) == 1
