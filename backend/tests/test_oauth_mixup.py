"""Mix-up protection of the connectors' OAuth client (plan M9 task 18, J13; ASVS 5.0
V10.2.2): every OAuth app has a callback of its own, `/api/ai/oauth/{id}/callback`, and
an authorization response must come back to the one its flow was started with; `iss`
(RFC 9207) is compared with the app's issuer when the server sends it or its metadata
promise it. The old shared callback answers only for flows started before the update."""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.oauth.models import OAuthFlow
from tests.factories_connectors import SHARED
from tests.factories_dms import People
from tests.factories_oauth import (
    CLIENTS,
    LEGACY_CALLBACK,
    PUBLIC_URL,
    authorize,
    callback_for,
    client_body,
    make_oauth_client,
    query_of,
)
from tests.support.oauth_stub import OAuthStub


async def _connector(people: People, stub: OAuthStub, name: str, **client: Any) -> tuple[Any, Any]:
    made = await make_oauth_client(people.admin, stub, name=name, **client)
    body = {"name": name, "auth_kind": "oauth", "oauth_client_id": made["id"]}
    response = await people.admin.post(SHARED, json=body)
    assert response.status_code == 201, response.text
    return made, response.json()


async def _status(people: People, path: str, query: dict[str, str]) -> str:
    response = await people.admin.get(path, params=query)
    assert response.status_code == 303, response.text
    return query_of(response.headers["location"])["status"]


async def test_callback_per_client_and_iss_checked(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    stub = oauth_ready
    made, connector = await _connector(ai_people, stub, "A", issuer=stub.url)
    own = f"/api/ai/oauth/{made['id']}/callback"
    assert made["callback_url"] == f"{PUBLIC_URL}{own}"
    assert made["issuer"] == stub.url and made["issuer_in_response"] is False

    # The flow names the app's own callback; the right issuer is accepted there.
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    assert dict(parse_qsl(urlsplit(url).query))["redirect_uri"] == f"{PUBLIC_URL}{own}"
    assert callback_for(url) == own
    stub.state.iss = stub.url
    assert await _status(ai_people, own, stub.state.authorize(url)) == "connected"

    # A foreign issuer: refused before any code goes to a token endpoint.
    exchanges = len(stub.state.token_requests("authorization_code"))
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    stub.state.iss = "https://elsewhere.test"
    assert await _status(ai_people, own, stub.state.authorize(url)) == "issuer_mismatch"
    assert len(stub.state.token_requests("authorization_code")) == exchanges

    # An app whose server promises `iss` (metadata): a response without it is refused.
    promised, other = await _connector(
        ai_people, stub, "B", issuer=stub.url, issuer_in_response=True
    )
    url = await authorize(ai_people.admin, SHARED, other["id"])
    stub.state.iss = None
    status = await _status(ai_people, callback_for(url), stub.state.authorize(url))
    assert status == "issuer_mismatch"
    assert len(stub.state.token_requests("authorization_code")) == exchanges

    # A response brought to another app's callback, or to the old shared one, is not
    # this flow's: the flow is used up, nothing is exchanged.
    stub.state.iss = stub.url
    for wrong in (f"/api/ai/oauth/{promised['id']}/callback", LEGACY_CALLBACK):
        url = await authorize(ai_people.admin, SHARED, connector["id"])
        assert await _status(ai_people, wrong, stub.state.authorize(url)) == "invalid"
    assert len(stub.state.token_requests("authorization_code")) == exchanges


async def test_the_shared_callback_finishes_flows_started_before_the_update(
    oauth_ready: OAuthStub, ai_people: People, session: AsyncSession
) -> None:
    stub = oauth_ready
    _, connector = await _connector(ai_people, stub, "Old")
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    # As started by the previous release: the shared redirect URI.
    legacy = f"{PUBLIC_URL}{LEGACY_CALLBACK}"
    await session.execute(update(OAuthFlow).values(redirect_uri=legacy))
    granted = stub.state.authorize(_with_redirect(url, legacy))
    assert await _status(ai_people, LEGACY_CALLBACK, granted) == "connected"
    (exchange,) = stub.state.token_requests("authorization_code")
    assert exchange.form["redirect_uri"] == legacy
    # Such a flow is not finished at the app's own callback either.
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    await session.execute(update(OAuthFlow).values(redirect_uri=legacy))
    status = await _status(ai_people, callback_for(url), stub.state.authorize(url))
    assert status == "invalid"
    assert await session.scalar(select(OAuthFlow)) is None


def _with_redirect(url: str, uri: str) -> str:
    """The authorization request as the previous release sent it (its redirect URI)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query)) | {"redirect_uri": uri}
    return parts._replace(query=urlencode(query)).geturl()


async def test_discovery_proposes_the_issuer_and_whether_it_answers_with_iss(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    oauth_ready.state.iss_in_metadata = True
    body = {"url": f"{oauth_ready.url}/mcp"}
    found = (await ai_people.admin.post(f"{CLIENTS}/discover", json=body)).json()
    assert found["issuer"] == oauth_ready.url and found["issuer_in_response"] is True
    oauth_ready.state.iss_in_metadata = False
    found = (await ai_people.admin.post(f"{CLIENTS}/discover", json=body)).json()
    assert found["issuer_in_response"] is False


async def test_an_app_that_promises_iss_needs_its_issuer(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    body = client_body(oauth_ready, name="No issuer", issuer_in_response=True)
    response = await ai_people.admin.post(CLIENTS, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "oauth_client.issuer_required"
