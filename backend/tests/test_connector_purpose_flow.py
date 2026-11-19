"""OAuth by purpose (plan M10 decision 18, task 13a): the authorization request carries
the purpose's extra parameters, the callback stays the app's own (one address at the
provider, M9b task 18) and the connector's purpose decides which right is checked and
where the browser goes next; calendar apps are managed with `calendar.manage`; MCP
connectors and apps behave as before."""

import uuid
from types import MappingProxyType
from urllib.parse import parse_qsl, urlsplit

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.config import get_settings
from app.core.errors import Forbidden, NotFound
from app.core.pagination import PageParams
from app.core.permissions import SYSTEM_ROLE_ACTIONS, Action
from app.core.principal import SystemRole
from app.modules.ai.secret_rotation import rotate_secrets
from app.modules.connectors import purposes
from app.modules.connectors.models import Connector, ConnectorScope
from app.modules.connectors.purposes import Purpose
from app.modules.oauth import protocol, tokens
from app.modules.oauth.clients import ClientService
from app.modules.oauth.flow import FlowService
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.schemas import ClientUpdate
from tests.factories_calendar import actor_of
from tests.factories_connectors import PERSONAL, make_connector
from tests.factories_dms import People
from tests.factories_oauth import (
    CLIENTS,
    callback_for,
    connect,
    make_oauth_client,
    query_of,
)
from tests.factories_purposes import (
    BASIC,
    calendar_client,
    calendar_connector,
    session_id_of,
    sync_on,
)
from tests.support.oauth_stub import OAuthStub

CALENDAR_EXTRA = {"access_type": "offline", "prompt": "consent"}


def _query(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query))


async def _fresh(session: AsyncSession, connector_id: uuid.UUID) -> Connector | None:
    return await session.get(Connector, connector_id, populate_existing=True)


def _url(allowed: frozenset[str] = frozenset(), **extra: str) -> dict[str, str]:
    made = protocol.authorization_url(
        "https://as.example.com/authorize",
        client_id="c",
        redirect_uri="https://herd.example/api/ai/oauth/x/callback",
        state="s",
        verifier="v" * 64,
        scopes="calendar",
        resource=None,
        extra=extra,
        allowed_extra=allowed,
    )
    return _query(made)


def test_the_authorization_url_carries_the_purposes_extra_parameters() -> None:
    plain = _url()
    assert "access_type" not in plain and "prompt" not in plain
    calendar = purposes.rule_for(Purpose.CALENDAR)
    extended = _url(calendar.extra_keys, **calendar.extra_authorization)
    assert {k: extended[k] for k in CALENDAR_EXTRA} == CALENDAR_EXTRA
    assert {k: v for k, v in extended.items() if k not in CALENDAR_EXTRA} == plain
    assert purposes.rule_for(Purpose.MCP).extra_authorization == {}
    for taken in ("state", "redirect_uri", "client_id", "code_challenge", "response_type"):
        with pytest.raises(ValueError):  # an extra never replaces what the flow sets
            _url(frozenset({taken}), **{taken: "x"})


@pytest.mark.parametrize(
    "key", ["response_mode", "request", "request_uri", "nonce", "login_hint", "state", "scope"]
)
def test_an_extra_parameter_outside_the_purposes_allow_list_is_refused(key: str) -> None:
    """R13a-9: an allow-list per purpose, not a deny-list of what the flow sets."""
    calendar = purposes.rule_for(Purpose.CALENDAR)
    for allowed in (frozenset(), calendar.extra_keys, purposes.rule_for(Purpose.MCP).extra_keys):
        with pytest.raises(ValueError):
            _url(allowed, **{key: "x"})
    assert calendar.extra_keys == frozenset(CALENDAR_EXTRA)
    assert purposes.rule_for(Purpose.MCP).extra_keys == frozenset()
    with pytest.raises(ValueError):  # a rule cannot carry an extra it does not allow
        purposes.Rule(
            calendar.use,
            calendar.manage,
            calendar.return_to,
            MappingProxyType({key: "x"}),
            calendar.extra_keys,
        )


async def test_the_callback_returns_to_the_page_of_its_purpose(
    people: People,
    oauth_egress: OAuthStub,
    public_url: str,
    secret_key: None,
    session: AsyncSession,
) -> None:
    """Alice has no AI assignment: the calendar's flow asks `calendar.sync` alone."""
    await sync_on(people.admin)
    alice = people.users["alice"]
    google = await calendar_client(session, people.users["admin"], oauth_egress)
    connector = await calendar_connector(session, alice, google)
    flows = FlowService(session)

    async def start() -> str:
        actor = await actor_of(session, alice)
        sid = await session_id_of(session, alice)
        return await flows.start(
            actor, sid, ConnectorScope.PERSONAL, connector.id, purpose=Purpose.CALENDAR
        )

    url = await start()
    query = _query(url)
    assert {k: query[k] for k in CALENDAR_EXTRA} == CALENDAR_EXTRA
    assert callback_for(url) == f"/api/ai/oauth/{google.id}/callback"  # one address
    r = await people.alice.get(callback_for(url), params=oauth_egress.state.authorize(url))
    assert r.status_code == 303
    location = r.headers["location"]
    assert urlsplit(location).path == "/calendar/accounts"
    assert query_of(location) == {"status": "connected", "connector": str(connector.id)}
    row = await _fresh(session, connector.id)
    assert row is not None and row.secret_ref is not None and row.secret_ref.startswith("enc:")
    # A stale state at the calendar app's callback goes back to the calendar page too.
    stale = await people.alice.get(callback_for(url), params={"state": "x", "code": "y"})
    assert stale.headers["location"] == "/calendar/accounts?status=invalid"
    # Without `calendar.sync` by the time the provider answers: invalid, nothing stored
    # (R13a-7: the tokens of the first connect stay as they were, no code exchanged).
    url = await start()
    await sync_on(people.admin, enabled=False)
    held = await _fresh(session, connector.id)
    assert held is not None
    kept = (held.secret_ref, held.refresh_token_ref, held.token_expires_at, held.version)
    exchanges = len(oauth_egress.state.token_requests("authorization_code"))
    r = await people.alice.get(callback_for(url), params=oauth_egress.state.authorize(url))
    assert query_of(r.headers["location"]) == {"status": "invalid"}
    assert urlsplit(r.headers["location"]).path == "/calendar/accounts"
    row = await _fresh(session, connector.id)
    assert row is not None
    assert (row.secret_ref, row.refresh_token_ref, row.token_expires_at, row.version) == kept
    assert len(oauth_egress.state.token_requests("authorization_code")) == exchanges
    # The MCP routes never start a calendar connector's flow.
    with pytest.raises(NotFound):
        await flows.start(
            await actor_of(session, alice),
            await session_id_of(session, alice),
            ConnectorScope.PERSONAL,
            connector.id,
        )


async def test_without_a_session_the_callback_returns_to_the_page_of_the_apps_purpose(
    people: People,
    client: AsyncClient,
    oauth_egress: OAuthStub,
    public_url: str,
    secret_key: None,
    session: AsyncSession,
) -> None:
    """R13a-5: a calendar user whose session ended during the provider's consent lands
    on the calendar's page, not on the AI one she may have no right to."""
    google = await calendar_client(session, people.users["admin"], oauth_egress)
    mcp = await make_oauth_client(people.admin, oauth_egress, name="Stub-App")
    expected = {
        google.id: "/calendar/accounts?status=invalid",
        uuid.UUID(mcp["id"]): "/ai/oauth/done?status=invalid",
        uuid.uuid4(): "/ai/oauth/done?status=invalid",  # no such app
    }
    for app_id, location in expected.items():
        path = f"/api/ai/oauth/{app_id}/callback"
        for params in ({"state": "x", "code": "y"}, {"error": "access_denied"}, {}):
            r = await client.get(path, params=params)  # no session at all
            assert (r.status_code, r.headers["location"]) == (303, location)
        signed_in = await people.alice.get(path, params={"code": "y"})  # no state
        assert signed_in.headers["location"] == location
    legacy = await client.get("/api/ai/oauth/callback", params={"state": "x"})
    assert legacy.headers["location"] == "/ai/oauth/done?status=invalid"


async def test_an_mcp_flow_returns_to_the_ai_page_as_before(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    app = await make_oauth_client(ai_people.admin, oauth_ready)
    body = {"name": "Stub", "auth_kind": "oauth", "oauth_client_id": app["id"]}
    made = (await ai_people.alice.post(PERSONAL, json=body)).json()
    url = (await ai_people.alice.post(f"{PERSONAL}/{made['id']}/authorize")).json()
    assert not set(CALENDAR_EXTRA) & set(_query(url["authorization_url"]))
    query = await connect(ai_people.alice, PERSONAL, made["id"], oauth_ready)
    assert query == {"status": "connected", "connector": made["id"], "scope": "personal"}


async def test_a_calendar_oauth_client_is_managed_with_calendar_manage(
    people: People,
    oauth_egress: OAuthStub,
    session: AsyncSession,
    secret_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await actor_of(session, people.users["admin"])
    calendar_apps, mcp_apps = ClientService(session, Purpose.CALENDAR), ClientService(session)
    # An admin without `ai.manage` still manages calendar apps, and none of the AI ones.
    without_ai = SYSTEM_ROLE_ACTIONS[SystemRole.ADMIN] - {Action.AI_MANAGE}
    monkeypatch.setitem(SYSTEM_ROLE_ACTIONS, SystemRole.ADMIN, without_ai)
    google = await calendar_client(session, people.users["admin"], oauth_egress)
    assert google.purpose == Purpose.CALENDAR
    listed = await calendar_apps.list(admin, PageParams(limit=100))
    assert [c.id for c in listed.items] == [google.id]
    assert (await calendar_apps.get(admin, google.id)).id == google.id
    r = await people.admin.get(CLIENTS)
    assert r.status_code == 404 and r.json()["error"]["code"] == "ai.not_found"
    # With `ai.manage` back, the AI administration still never sees the calendar app.
    monkeypatch.setitem(SYSTEM_ROLE_ACTIONS, SystemRole.ADMIN, without_ai | {Action.AI_MANAGE})
    mcp = await make_oauth_client(people.admin, oauth_egress, name="Stub-App")
    assert [c.id for c in (await mcp_apps.list(admin, PageParams(limit=100))).items] == [
        uuid.UUID(mcp["id"])
    ]
    with pytest.raises(NotFound):
        await mcp_apps.get(admin, google.id)
    with pytest.raises(NotFound):
        await calendar_apps.get(admin, uuid.UUID(mcp["id"]))
    # Without `calendar.manage`: refused (403, the calendar's way), members too.
    no_calendar = SYSTEM_ROLE_ACTIONS[SystemRole.ADMIN] - {Action.CALENDAR_MANAGE}
    monkeypatch.setitem(SYSTEM_ROLE_ACTIONS, SystemRole.ADMIN, no_calendar)
    with pytest.raises(Forbidden):
        await calendar_apps.list(admin, PageParams(limit=100))
    with pytest.raises(Forbidden):
        await calendar_apps.get(await actor_of(session, people.users["alice"]), google.id)
    assert purposes.rule_for(Purpose.MCP).manage == Action.AI_MANAGE


async def test_a_calendar_apps_new_endpoint_disconnects_its_connectors(
    people: People, oauth_egress: OAuthStub, session: AsyncSession, secret_key: None
) -> None:
    """`connectors/moving.py` holds for calendar apps: a secret goes only where given."""
    await sync_on(people.admin)
    admin = await actor_of(session, people.users["admin"])
    google = await calendar_client(session, people.users["admin"], oauth_egress)
    connector = await calendar_connector(session, people.users["alice"], google)
    other = await calendar_connector(session, people.users["alice"])
    change = ClientUpdate(token_endpoint=f"{oauth_egress.url}/token2", version=google.version)
    await ClientService(session, Purpose.CALENDAR).update(admin, google.id, change)
    assert await _fresh(session, connector.id) is None
    assert await _fresh(session, other.id) is not None  # not through that app


async def test_mcp_connectors_behave_as_before(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    made = await make_connector(ai_people.admin, PERSONAL)
    app = await make_oauth_client(ai_people.admin, oauth_ready)
    row = await _fresh(session, uuid.UUID(made["id"]))
    client = await session.get(OAuthClient, uuid.UUID(app["id"]))
    assert row is not None and client is not None
    assert (row.purpose, client.purpose) == (Purpose.MCP, Purpose.MCP)
    rule = purposes.rule_for(Purpose.MCP)
    assert (rule.use, rule.manage, rule.return_to) == (
        Action.AI_USE,
        Action.AI_MANAGE,
        "/ai/oauth/done",
    )
    # Renewal of an MCP OAuth connector, under its row lock, as in M8.
    body = {"name": "Stub", "auth_kind": "oauth", "oauth_client_id": app["id"]}
    oauth = (await ai_people.alice.post(PERSONAL, json=body)).json()
    await connect(ai_people.alice, PERSONAL, oauth["id"], oauth_ready)
    old = oauth_ready.state.issued[-1]
    renewed = await tokens.renew(row.org_id, uuid.UUID(oauth["id"]), used=old)
    assert renewed == {"Authorization": f"Bearer {oauth_ready.state.issued[-1]}"}
    # A moved MCP app still disconnects its MCP connectors (`moving.py`).
    moved = await ai_people.admin.patch(
        f"{CLIENTS}/{app['id']}",
        json={"token_endpoint": f"{oauth_ready.url}/token2", "version": 1},
    )
    assert moved.status_code == 200, moved.text
    assert await _fresh(session, uuid.UUID(oauth["id"])) is None


async def test_key_rotation_covers_calendar_connectors_and_apps(
    people: People,
    oauth_egress: OAuthStub,
    session: AsyncSession,
    secret_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await sync_on(people.admin)
    google = await calendar_client(session, people.users["admin"], oauth_egress)
    connector = await calendar_connector(session, people.users["alice"])
    before = (connector.secret_ref, google.client_secret_ref)
    monkeypatch.setattr(get_settings(), "secret_key_previous", get_settings().secret_key)
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr("n" * 48))
    await rotate_secrets(session)
    rows = (await session.scalars(select(Connector).where(Connector.id == connector.id))).all()
    assert rows[0].secret_ref != before[0] and google.client_secret_ref != before[1]
    assert rows[0].secret_ref is not None
    assert secrets.resolve(rows[0].secret_ref).get_secret_value() == BASIC
