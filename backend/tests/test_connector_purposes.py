"""The purpose of connectors and OAuth clients (plan M10 decision 18, task 13a): the M8
services show and change only `mcp`; a `calendar` access belongs to its person, needs
`calendar.sync` (not `ai.use`) and is never used for an MCP server, nor an MCP one for a
calendar. Here: the M8 routes against calendar rows, the rights, the credential."""

import uuid
from typing import Any

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.modules.connectors import credentials, purposes
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope
from app.modules.connectors.purposes import Purpose
from app.modules.connectors.service import ConnectorService
from app.modules.mcp_servers.endpoints import connector_for
from app.modules.mcp_servers.models import McpServer
from app.modules.oauth import tokens
from app.web.public import create_public_app
from tests.factories_calendar import actor_of
from tests.factories_connectors import PERSONAL, SHARED, make_connector
from tests.factories_dms import People
from tests.factories_mcp import make_server
from tests.factories_oauth import CLIENTS, make_oauth_client
from tests.factories_purposes import BASIC, ORIGIN, calendar_client, calendar_connector, sync_on
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub

SERVERS = "/api/ai/mcp-servers"
PREFIXES = (
    "/api/ai/connectors",
    "/api/ai/my-connectors",
    "/api/ai/oauth-clients",
    "/api/ai/oauth/",
    "/api/ai/mcp-servers",
    "/api/ai/my-mcp-servers",
)
# Routes that name no connector or client by id and list neither: what they take is
# checked below (`_creating`) or cannot name a calendar row at all.
WITHOUT_IDS = {
    ("POST", "/api/ai/oauth-clients/discover"),  # an address; stores nothing
    ("POST", "/api/ai/oauth-clients"),  # a new app names no other
    ("POST", "/api/ai/mcp-servers/{server_id}/refresh"),
    ("POST", "/api/ai/mcp-servers/{server_id}/test"),
    ("GET", "/api/ai/mcp-servers/{server_id}"),
    ("DELETE", "/api/ai/mcp-servers/{server_id}"),
    ("GET", "/api/ai/mcp-servers/{server_id}/tools"),
    ("PATCH", "/api/ai/mcp-servers/{server_id}/tools/{tool_id}"),
    ("POST", "/api/ai/mcp-servers/{server_id}/tools/{tool_id}/approve"),
    ("POST", "/api/ai/mcp-servers/{server_id}/tools/{tool_id}/block"),
    # A calendar app's own callback is its callback: `test_connector_purpose_flow.py`.
    ("GET", "/api/ai/oauth/{client_id}/callback"),
    ("GET", "/api/ai/oauth/callback"),
}

# Routes that take a connector or client id in their body: `_creating`.
CREATING = {
    ("POST", "/api/ai/connectors"),
    ("POST", "/api/ai/my-connectors"),
    ("POST", "/api/ai/mcp-servers"),
    ("PATCH", "/api/ai/mcp-servers/{server_id}"),
}


def _routes() -> list[tuple[str, str]]:
    found = []
    for context in iter_route_contexts(create_public_app().routes):
        route, path = context.original_route, context.path
        if isinstance(route, APIRoute) and path.startswith(PREFIXES):
            found += [(method, path) for method in sorted(route.methods)]
    return found


def _body(method: str, path: str) -> dict[str, Any] | None:
    if method == "PATCH":
        return {"name": "Umbenannt", "version": 1}
    if path.endswith("/disconnect"):
        return {"version": 1}
    return None


async def _same_as_unknown(client: Any, method: str, path: str, ids: list[uuid.UUID]) -> None:
    """Each id answers exactly like an id nobody has: 404 with the area's code."""
    name = "{connector_id}" if "{connector_id}" in path else "{client_id}"
    query = "?version=1" if method == "DELETE" else ""

    async def call(value: object) -> tuple[int, str]:
        url = path.replace(name, str(value)) + query
        r = await client.request(method, url, json=_body(method, path))
        return r.status_code, r.json()["error"]["code"]

    unknown = await call(uuid.uuid4())
    assert unknown[0] == 404, (method, path, unknown)
    for value in ids:
        assert await call(value) == unknown, (method, path)


async def _refused_alike(
    people: People, method: str, url: str, body: dict[str, Any], key: str, ids: list[uuid.UUID]
) -> None:
    async def call(value: object) -> tuple[int, str | None]:
        r = await people.admin.request(method, url, json={**body, key: str(value)})
        return r.status_code, r.json().get("error", {}).get("code")

    unknown = await call(uuid.uuid4())
    assert unknown[0] == 422, (url, unknown)
    for value in ids:
        assert await call(value) == unknown, (method, url, key)


async def _creating(people: People, server: dict[str, Any], cal: dict[str, uuid.UUID]) -> None:
    """Creating and changing what may name a connector or a client: a calendar one is
    refused exactly like an unknown id."""
    connectors, clients = [cal["header"], cal["oauth"]], [cal["client"]]
    url, scope = server["url"], "connector_scope"
    oauth = {"auth_kind": "oauth"}
    await _refused_alike(people, "POST", SHARED, {"name": "A", **oauth}, "oauth_client_id", clients)
    await _refused_alike(
        people, "POST", PERSONAL, {"name": "B", **oauth}, "oauth_client_id", clients
    )
    shared = {"name": "S1", "url": url, scope: "shared"}
    await _refused_alike(people, "POST", SERVERS, shared, "connector_id", connectors)
    personal = {"name": "S2", "url": url, scope: "personal"}
    await _refused_alike(people, "POST", SERVERS, personal, "oauth_client_id", clients)
    change = {scope: "shared", "version": 1}
    path = f"{SERVERS}/{server['id']}"
    await _refused_alike(people, "PATCH", path, change, "connector_id", connectors)


async def test_every_existing_connector_route_ignores_calendar_connectors(
    oauth_ready: OAuthStub, mcp_stub: McpStub, ai_people: People, session: AsyncSession
) -> None:
    await sync_on(ai_people.admin)
    admin = ai_people.users["admin"]
    google = await calendar_client(session, admin, oauth_ready)
    cal = {
        "header": (await calendar_connector(session, admin)).id,
        "oauth": (await calendar_connector(session, admin, google)).id,
        "client": google.id,
    }
    mine = {
        str((await make_connector(ai_people.admin))["id"]),
        str((await make_connector(ai_people.admin, PERSONAL, name="Eigen"))["id"]),
        str((await make_oauth_client(ai_people.admin, oauth_ready, name="Stub-App"))["id"]),
    }
    server = await make_server(ai_people.admin, mcp_stub)
    seen: set[tuple[str, str]] = set()
    for method, path in _routes():
        if (method, path) in WITHOUT_IDS:
            continue
        seen.add((method, path))
        if "{connector_id}" in path:
            await _same_as_unknown(ai_people.admin, method, path, [cal["header"], cal["oauth"]])
        elif "{client_id}" in path:
            await _same_as_unknown(ai_people.admin, method, path, [cal["client"]])
        elif method == "GET":
            r = await ai_people.admin.get(path, params={"limit": 100})
            assert r.status_code == 200, (path, r.text)
            listed = {item["id"] for item in r.json()["items"]}
            assert not listed & {str(v) for v in cal.values()}, path
            assert listed & mine or path.endswith("mcp-servers"), path
        else:
            assert (method, path) in CREATING, (method, path)
    await _creating(ai_people, server, cal)
    assert ("GET", PERSONAL) in seen and ("PATCH", f"{CLIENTS}/{{client_id}}") in seen
    for connector_id in (cal["header"], cal["oauth"]):
        row = await _fresh(session, connector_id)
        assert row.version == 1 and row.name == f"calendar:{row.id}"  # untouched


async def _fresh(session: AsyncSession, connector_id: uuid.UUID) -> Connector:
    row = await session.get(Connector, connector_id, populate_existing=True)
    assert row is not None
    return row


async def test_a_calendar_connector_needs_calendar_sync_not_ai_use(
    people: People, session: AsyncSession, secret_key: None
) -> None:
    alice = people.users["alice"]  # no AI assignment: no `ai.use`
    with pytest.raises(Forbidden):  # the switch is off: nobody holds `calendar.sync`
        await calendar_connector(session, alice)
    await sync_on(people.admin)
    made = await calendar_connector(session, alice)
    assert (made.purpose, made.scope, made.owner_id) == (Purpose.CALENDAR, "personal", alice.id)
    assert made.auth_kind == AuthKind.HEADER and made.header_name == "Authorization"
    assert made.secret_ref is not None and made.secret_ref.startswith("enc:")
    assert BASIC not in made.secret_ref
    with pytest.raises(Forbidden):  # guests never hold `calendar.sync`
        await calendar_connector(session, people.users["gast"])
    # An MCP connector still needs `ai.use`, as before (404 `ai.not_found`).
    r = await people.alice.post(
        PERSONAL, json={"name": "X", "auth_kind": "bearer", "secret": {"value": "x"}}
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "ai.not_found"
    rule = purposes.rule_for(Purpose.CALENDAR)
    assert (rule.use.value, rule.manage.value) == ("calendar.sync", "calendar.manage")


async def test_creating_a_calendar_connector_checks_what_it_is_given(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    await sync_on(ai_people.admin)
    alice = ai_people.users["alice"]
    actor = await actor_of(session, alice)
    mcp_app = await make_oauth_client(ai_people.admin, oauth_ready)

    async def create(**fields: Any) -> Connector:
        given: dict[str, Any] = {"kind": AuthKind.HEADER, "origin": ORIGIN}
        given |= {"header_name": "Authorization", "secret": SecretStr(BASIC)} | fields
        return await purposes.create_personal(session, actor, purpose=Purpose.CALENDAR, **given)

    for origin in (
        "http://caldav.example.com",
        "https://u:p@caldav.example.com",
        "https://caldav.example.com/dav/",
        "https://",
        "caldav.example.com",
    ):
        with pytest.raises(ValidationFailed) as refused:
            await create(origin=origin)
        assert refused.value.code == "connector.origin_invalid", origin
    with pytest.raises(ValidationFailed) as refused:  # an MCP app is not a calendar app
        await create(
            kind=AuthKind.OAUTH,
            header_name=None,
            secret=None,
            oauth_client_id=uuid.UUID(mcp_app["id"]),
        )
    assert refused.value.code == "connector.oauth_client_invalid"
    with pytest.raises(ValidationFailed) as refused:
        await create(header_name=None)
    assert refused.value.code == "connector.header_name_invalid"
    with pytest.raises(ValidationFailed):
        await create(secret=None)
    two = [await create(), await create(origin="https://caldav.example.com:8443")]
    assert len({c.name for c in two}) == 2  # a person may connect one place twice


async def test_a_calendar_connector_is_never_used_for_an_mcp_server(
    oauth_ready: OAuthStub, mcp_stub: McpStub, ai_people: People, session: AsyncSession
) -> None:
    await sync_on(ai_people.admin)
    admin = ai_people.users["admin"]
    calendar = await calendar_connector(session, admin)
    with pytest.raises(credentials.WrongPurpose):  # an MCP call asks for `mcp`
        credentials.headers_for(calendar)
    with pytest.raises(credentials.WrongPurpose):
        await credentials.credential_headers(calendar)
    assert credentials.headers_for(calendar, Purpose.CALENDAR) == {"Authorization": BASIC}
    # Named as a shared server's connector behind the service's back: never found.
    made = await make_server(ai_people.admin, mcp_stub)
    found = await session.get(McpServer, uuid.UUID(made["id"]))
    assert found is not None
    server = McpServer(**{c: getattr(found, c) for c in ("id", "org_id", "url")})
    server.connector_scope, server.connector_id = "shared", calendar.id
    assert await connector_for(session, server, admin.id) is None
    # The database refuses to bind one to a server, to share it, or to let it
    # connect through an MCP app (each change alone breaks only that rule).
    mcp_app = uuid.UUID((await make_oauth_client(ai_people.admin, oauth_ready))["id"])
    google = await calendar_connector(
        session, admin, await calendar_client(session, admin, oauth_ready)
    )
    changes: list[tuple[uuid.UUID, dict[str, Any], str]] = [
        (calendar.id, {"mcp_server_id": server.id}, "ck_connector_purpose_personal"),
        (calendar.id, {"scope": "shared", "owner_id": None}, "ck_connector_purpose_personal"),
        (google.id, {"oauth_client_id": mcp_app}, "fk_connector_oauth_client_purpose"),
    ]
    for connector_id, fields, constraint in changes:
        async with session.begin_nested() as nested:
            row = await _fresh(session, connector_id)
            for name, value in fields.items():
                setattr(row, name, value)
            with pytest.raises(IntegrityError) as broken:
                await session.flush()
            assert constraint in str(broken.value.orig), constraint
            await nested.rollback()


async def test_an_mcp_connector_is_never_used_for_a_calendar(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession, oauth_units: None
) -> None:
    await sync_on(ai_people.admin)
    made = await make_connector(ai_people.admin, PERSONAL)
    connector = await _fresh(session, uuid.UUID(made["id"]))
    assert connector.purpose == Purpose.MCP
    assert credentials.headers_for(connector) == {"Authorization": "Bearer tok-1"}
    with pytest.raises(credentials.WrongPurpose):
        credentials.headers_for(connector, Purpose.CALENDAR)
    with pytest.raises(credentials.WrongPurpose):
        await credentials.credential_headers(connector, Purpose.CALENDAR)
    # A renewal asked for one purpose never touches the other's connector.
    calendar = await calendar_connector(
        session,
        ai_people.users["admin"],
        await calendar_client(session, ai_people.users["admin"], oauth_ready),
    )
    with pytest.raises(credentials.WrongPurpose):
        await tokens.renew(calendar.org_id, calendar.id, used=None)
    with pytest.raises(credentials.WrongPurpose):
        await tokens.renew(connector.org_id, connector.id, used=None, purpose=Purpose.CALENDAR)
    # And the M8 services find no calendar connector by id.
    actor = await actor_of(session, ai_people.users["admin"])
    with pytest.raises(NotFound):
        await ConnectorService(session).get(actor, ConnectorScope.PERSONAL, calendar.id)
