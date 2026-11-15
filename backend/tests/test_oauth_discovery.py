"""Discovering an MCP server's authorization server (plan M8 task 8; MCP authorization
2025-11-25): protected resource metadata (RFC 9728) from the server's 401 challenge,
else from the well-known URIs; then the authorization server's metadata (RFC 8414,
OpenID discovery). Every request through the egress guard; the answer is a proposal
for an OAuth client, nothing is stored."""

from typing import Any

from tests.factories_dms import People
from tests.factories_oauth import CLIENTS
from tests.support.oauth_stub import OAuthStub

DISCOVER = f"{CLIENTS}/discover"


async def _discover(people: People, url: str) -> dict[str, Any]:
    response = await people.admin.post(DISCOVER, json={"url": url})
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def test_well_known_metadata_proposes_a_client(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    found = await _discover(ai_people, f"{oauth_ready.url}/mcp")
    assert found == {
        "status": "ok",
        "resource": f"{oauth_ready.url}/mcp",
        "issuer": oauth_ready.url,
        "authorization_endpoint": f"{oauth_ready.url}/authorize",
        "token_endpoint": f"{oauth_ready.url}/token",
        "revocation_endpoint": f"{oauth_ready.url}/revoke",
        "scopes": "mcp",
        "pkce": True,
        "registration": False,
    }


async def test_the_401_challenge_names_metadata_and_scope(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    oauth_ready.state.challenge = True
    oauth_ready.state.challenge_scope = "mcp read"
    found = await _discover(ai_people, f"{oauth_ready.url}/mcp")
    assert found["status"] == "ok" and found["scopes"] == "mcp read"


async def test_without_pkce_or_with_another_resource(
    oauth_ready: OAuthStub, ai_people: People
) -> None:
    oauth_ready.state.pkce_in_metadata = False
    found = await _discover(ai_people, f"{oauth_ready.url}/mcp")
    assert found["status"] == "ok" and found["pkce"] is False
    oauth_ready.state.resource_override = "https://elsewhere.example/mcp"
    mismatch = await _discover(ai_people, f"{oauth_ready.url}/mcp")
    assert mismatch["status"] == "resource_mismatch"
    assert mismatch["token_endpoint"] is None


async def test_nothing_to_find_and_the_guard(oauth_ready: OAuthStub, ai_people: People) -> None:
    missing = await _discover(ai_people, f"{oauth_ready.url}/nothing")
    assert missing["status"] == "no_metadata"
    blocked = await _discover(ai_people, "https://internal.example/mcp")
    assert blocked["status"] in {"blocked", "unreachable"}
    refused = await ai_people.admin.post(DISCOVER, json={"url": "https://10.0.0.1/mcp"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "oauth_client.url_not_allowed"
    hidden = await ai_people.alice.post(DISCOVER, json={"url": f"{oauth_ready.url}/mcp"})
    assert hidden.json()["error"]["code"] == "ai.not_found"
