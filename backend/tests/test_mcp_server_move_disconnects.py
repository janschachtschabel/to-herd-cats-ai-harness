"""Module review M8 1, finding 4: a person's own connector is bound to a server, not to an address. When someone
with `ai.manage` gives the server another URL, the tools' approvals are withdrawn
("the tools there are not the ones approved", `mcp_servers/service.py`), but every
person's personal connector stays bound: as soon as a tool is approved again, the
next run of that person sends their own secret (a PAT, an OAuth token) to the new
address. The person is not asked and not told ("my connections" shows a server's
name, never its address), although a personal connector is hidden even from admins.
Now a new origin of the server (or new endpoints of its OAuth client) disconnects
every connector given for the old place; people see the address and connect again."""

import ssl
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress
from app.modules.audit.models import AuditLog
from app.modules.connectors.moving import moved_origin
from tests.factories_connectors import PERSONAL as MY_CONNECTORS
from tests.factories_connectors import SHARED, make_connector
from tests.factories_dms import People
from tests.factories_external import Ext, _resolve, call
from tests.factories_mcp import SERVERS, approve, make_server, mcp_network
from tests.factories_oauth import CLIENTS, connect, make_oauth_client
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub

MY_SERVERS = "/api/ai/my-mcp-servers"
ELSEWHERE = "https://elsewhere.test/mcp"

SECRET = "pat-nur-fuer-alice"


async def test_a_moved_server_does_not_get_the_secret_a_person_gave_the_old_address(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A correct system sends a person's own secret only where that person connected
    it: after the server's address changed, their connector is not used until they
    connect again (the call answers "not connected")."""
    await ext.patch_server(connector_scope="personal")
    await make_connector(
        ext.bench.people.alice,
        MY_CONNECTORS,
        mcp_server_id=ext.server["id"],
        secret={"value": SECRET},
    )
    elsewhere = McpStub().start()
    try:
        network = mcp_network(ext.stub, _resolve)
        context = ssl.create_default_context(cafile=str(ext.stub.cert_path))
        context.load_verify_locations(cafile=str(elsewhere.cert_path))
        monkeypatch.setattr(
            egress,
            "_network",
            egress.Network(
                resolver=network.resolver, ssl_context=context, extra_allowed=network.extra_allowed
            ),
        )
        await ext.patch_server(url=elsewhere.url)  # someone with `ai.manage` moves it
        r = await ext.admin.post(f"/api/ai/mcp-servers/{ext.server['id']}/refresh")
        assert r.status_code == 200 and r.json()["status"] == "ok", r.text
        for tool in (await ext.tools()).values():
            await approve(ext.admin, ext.server["id"], tool)
        await ext.grant(search_issues="allow")
        name = await ext.name("search_issues")
        ext.bench.stub.state.replies.extend([call(name, q="meine"), {"content": "Erledigt."}])
        await ext.bench.say("Such meine Issues")
        await ext.bench.run_next()
        assert SECRET not in elsewhere.state.texts(), "the new address got Alice's own secret"
    finally:
        elsewhere.stop()


def test_the_origin_counts_not_the_path() -> None:
    assert not moved_origin("https://a.test/mcp", "https://A.test:443/other/")
    assert moved_origin("https://a.test/mcp", "https://a.test:8443/mcp")
    assert moved_origin("https://a.test/mcp", "https://b.test/mcp")


async def _patch(admin: AsyncClient, server_id: object, **fields: Any) -> dict[str, Any]:
    version = (await admin.get(f"{SERVERS}/{server_id}")).json()["version"]
    r = await admin.patch(f"{SERVERS}/{server_id}", json={**fields, "version": version})
    assert r.status_code == 200, r.text
    patched: dict[str, Any] = r.json()
    return patched


async def _mine(client: AsyncClient) -> dict[str, dict[str, Any]]:
    r = await client.get(MY_SERVERS)
    assert r.status_code == 200, r.text
    return {s["name"]: s for s in r.json()["items"]}


async def _audit(session: AsyncSession, action: str) -> dict[str, Any]:
    rows = await session.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    )
    return dict(list(rows)[-1].details)


async def test_a_new_origin_disconnects_personal_connectors_and_a_path_does_not(
    ai_people: People, mcp_egress: McpStub, session: AsyncSession
) -> None:
    made = await make_server(ai_people.admin, mcp_egress, connector_scope="personal")
    mine = await make_connector(ai_people.alice, MY_CONNECTORS, mcp_server_id=made["id"])
    shown = (await _mine(ai_people.alice))["Tracker"]
    assert shown["url"] == mcp_egress.url and shown["connected"] is True
    assert mine["server_urls"] == [mcp_egress.url]
    await _patch(ai_people.admin, made["id"], url=mcp_egress.url + "/")  # the path only
    assert (await _mine(ai_people.alice))["Tracker"]["connected"] is True
    assert (await _audit(session, "mcp_server.updated")) == {"fields": ["url"]}
    await _patch(ai_people.admin, made["id"], url=ELSEWHERE)
    shown = (await _mine(ai_people.alice))["Tracker"]
    assert shown["url"] == ELSEWHERE and shown["connected"] is False
    gone = await ai_people.alice.get(f"{MY_CONNECTORS}/{mine['id']}")
    assert gone.status_code == 404
    assert await _audit(session, "mcp_server.updated") == {
        "fields": ["url"],
        "moved": {"personal_connectors_disconnected": 1, "shared_connector_detached": False},
    }


async def test_a_moved_server_keeps_its_shared_connector_only_when_asked(
    ai_people: People, mcp_egress: McpStub
) -> None:
    shared = await make_connector(ai_people.admin, SHARED)
    made = await make_server(
        ai_people.admin, mcp_egress, connector_scope="shared", connector_id=shared["id"]
    )
    assert (await ai_people.admin.get(f"{SHARED}/{shared['id']}")).json()["server_urls"] == [
        mcp_egress.url
    ]
    kept = await _patch(ai_people.admin, made["id"], url=ELSEWHERE, keep_shared_connector=True)
    assert kept["connector_scope"] == "shared" and kept["connector_id"] == shared["id"]
    unchanged = {"connector_scope": "shared", "connector_id": shared["id"]}  # as a form sends
    detached = await _patch(ai_people.admin, made["id"], url=mcp_egress.url, **unchanged)
    assert detached["connector_scope"] == "none" and detached["connector_id"] is None
    named = await _patch(
        ai_people.admin,
        made["id"],
        url=ELSEWHERE,
        connector_scope="shared",
        connector_id=shared["id"],
    )
    assert named["connector_id"] == shared["id"]  # chosen with the move: kept knowingly


async def _connected(people: People, stub: OAuthStub, base: str, who: str, client: str) -> str:
    body = {"name": f"Stub {who}", "auth_kind": "oauth", "oauth_client_id": client}
    r = await getattr(people, who).post(base, json=body)
    assert r.status_code == 201, r.text
    await connect(getattr(people, who), base, r.json()["id"], stub)
    connector_id: str = r.json()["id"]
    return connector_id


async def test_new_client_endpoints_disconnect_and_revoke_at_the_old_provider(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    client = await make_oauth_client(ai_people.admin, oauth_ready)
    personal = await _connected(ai_people, oauth_ready, MY_CONNECTORS, "alice", client["id"])
    alices = oauth_ready.state.issued[-1]
    shared = await _connected(ai_people, oauth_ready, SHARED, "admin", client["id"])
    body = {"version": client["version"], "name": "Umbenannt"}
    r = await ai_people.admin.patch(f"{CLIENTS}/{client['id']}", json=body)
    assert r.status_code == 200, r.text  # nothing moved: nothing disconnected
    assert (await ai_people.alice.get(f"{MY_CONNECTORS}/{personal}")).status_code == 200
    moved = {
        "version": r.json()["version"],
        "token_endpoint": f"{oauth_ready.url}/token2",
        "keep_shared_connectors": True,
    }
    r = await ai_people.admin.patch(f"{CLIENTS}/{client['id']}", json=moved)
    assert r.status_code == 200, r.text
    assert (await ai_people.alice.get(f"{MY_CONNECTORS}/{personal}")).status_code == 404
    assert alices in oauth_ready.state.revoked  # at the old provider, after the commit
    assert (await ai_people.admin.get(f"{SHARED}/{shared}")).json()["has_secret"] is True
    assert await _audit(session, "oauth_client.updated") == {
        "fields": ["token_endpoint"],
        "moved": {"personal_connectors_disconnected": 1, "shared_connectors_disconnected": 0},
    }
    again = {"version": r.json()["version"], "authorization_endpoint": f"{oauth_ready.url}/a2"}
    r = await ai_people.admin.patch(f"{CLIENTS}/{client['id']}", json=again)
    assert r.status_code == 200, r.text
    assert (await ai_people.admin.get(f"{SHARED}/{shared}")).json()["has_secret"] is False


async def test_deleting_a_server_revokes_the_personal_tokens_bound_to_it(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    """Module review M8 1, finding 8: the personal connectors went with the server by
    the foreign key, their tokens still valid at the provider."""
    client = await make_oauth_client(ai_people.admin, oauth_ready)
    made = await make_server(
        ai_people.admin, mcp_stub, connector_scope="personal", oauth_client_id=client["id"]
    )
    body = {
        "name": "Mine",
        "auth_kind": "oauth",
        "oauth_client_id": client["id"],
        "mcp_server_id": made["id"],
    }
    mine = (await ai_people.alice.post(MY_CONNECTORS, json=body)).json()
    await connect(ai_people.alice, MY_CONNECTORS, mine["id"], oauth_ready)
    alices = oauth_ready.state.issued[-1]
    version = (await ai_people.admin.get(f"{SERVERS}/{made['id']}")).json()["version"]
    r = await ai_people.admin.delete(f"{SERVERS}/{made['id']}", params={"version": version})
    assert r.status_code == 204, r.text
    assert alices in oauth_ready.state.revoked
    assert await _audit(session, "mcp_server.deleted") == {
        "name": "Tracker",
        "personal_connectors_disconnected": 1,
    }
