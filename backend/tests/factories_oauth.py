"""OAuth fixtures: `oauth_stub` (a local authorization server, https for `oauth.test`,
reset per test), `oauth_egress` (the egress guard resolving `*.test` to 127.0.0.1 and
trusting both the OAuth and the MCP stub's certificates), `public_url` (the
configured public address the redirect URI is derived from) and `oauth_units` (the
token renewal's own transactions on the test session), plus helpers to set up an
OAuth client and connect a connector through the API."""

import ipaddress
import ssl
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress
from app.core.config import get_settings
from app.core.egress import Network
from app.modules.oauth import tokens
from tests.factories_mcp import resolve_test_names
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub

CLIENTS = "/api/ai/oauth-clients"
# The shared callback of releases before M9b task 18 (J13): it answers only for flows
# started with it; every flow since names its app's own (`callback_for`).
LEGACY_CALLBACK = "/api/ai/oauth/callback"
PUBLIC_URL = "https://herd.example"


@pytest.fixture(scope="session")
def _oauth_stub() -> Iterator[OAuthStub]:
    stub = OAuthStub().start()
    yield stub
    stub.stop()


@pytest.fixture
def oauth_stub(_oauth_stub: OAuthStub) -> Iterator[OAuthStub]:
    _oauth_stub.state.reset()
    yield _oauth_stub
    _oauth_stub.state.reset()


@pytest.fixture
def public_url(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(get_settings(), "public_url", PUBLIC_URL)
    return PUBLIC_URL


@pytest.fixture
def oauth_egress(
    oauth_stub: OAuthStub, mcp_stub: McpStub, monkeypatch: pytest.MonkeyPatch
) -> OAuthStub:
    context = ssl.create_default_context(cafile=str(oauth_stub.cert_path))
    context.load_verify_locations(cafile=str(mcp_stub.cert_path))
    network = Network(
        resolver=resolve_test_names,
        ssl_context=context,
        extra_allowed=(ipaddress.ip_network("127.0.0.1/32"),),
    )
    monkeypatch.setattr(egress, "_network", network)
    return oauth_stub


@pytest.fixture
def oauth_units(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Token renewal runs in a transaction of its own; here a savepoint of the test's."""

    @asynccontextmanager
    async def unit() -> AsyncIterator[AsyncSession]:
        async with session.begin_nested():
            yield session

    monkeypatch.setattr(tokens, "open_unit", unit)


@pytest.fixture
def oauth_ready(
    ai_people: Any, oauth_egress: OAuthStub, public_url: str, oauth_units: None
) -> OAuthStub:
    """Everything an OAuth test needs: people with AI, the stub, the address, units."""
    return oauth_egress


def client_body(stub: OAuthStub, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Stub-App",
        "authorization_endpoint": f"{stub.url}/authorize",
        "token_endpoint": f"{stub.url}/token",
        "revocation_endpoint": f"{stub.url}/revoke",
        "client_id": stub.state.client_id,
        "client_secret": {"value": stub.state.client_secret},
        "scopes": "mcp read",
        "resource": f"{stub.url}/mcp",
    }
    body.update(fields)
    return body


async def make_oauth_client(admin: AsyncClient, stub: OAuthStub, **fields: Any) -> dict[str, Any]:
    response = await admin.post(CLIENTS, json=client_body(stub, **fields))
    assert response.status_code == 201, response.text
    made: dict[str, Any] = response.json()
    return made


async def authorize(client: AsyncClient, base: str, connector_id: object) -> str:
    response = await client.post(f"{base}/{connector_id}/authorize")
    assert response.status_code == 200, response.text
    url: str = response.json()["authorization_url"]
    return url


def callback_for(url: str) -> str:
    """The path of the callback an authorization request names (its app's own)."""
    return urlsplit(dict(parse_qsl(urlsplit(url).query))["redirect_uri"]).path


def query_of(location: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(location).query))


async def connect(
    client: AsyncClient, base: str, connector_id: object, stub: OAuthStub
) -> dict[str, str]:
    """Start the flow, let the stub approve, come back to the callback; the query of
    the page the callback sends the browser to."""
    url = await authorize(client, base, connector_id)
    response = await client.get(callback_for(url), params=stub.state.authorize(url))
    assert response.status_code == 303, response.text
    return query_of(response.headers["location"])
