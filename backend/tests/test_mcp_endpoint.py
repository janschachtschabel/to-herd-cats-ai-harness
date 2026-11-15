"""Plan M8 task 2: the `/mcp` endpoint itself (decisions 1, 5 and 6). Stateless
Streamable HTTP, one JSON answer per request, tools only; the token is resolved on
every request; whatever is wrong with it answers the same 401 in the MCP form;
browsers (any `Origin`) are refused; no sessions, no server streams."""

import httpx2
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from tests.factories_mcp_endpoint import INITIALIZE, URL, Connect, rpc, text_of
from tests.factories_tokens import mcp_on, new_token

READ_TOOLS = {"search", "read_page", "read_ticket", "list_tree", "list_versions", "search_tickets"}


async def test_a_real_client_lists_the_read_tools_of_the_catalog(
    owner: AsyncClient, member_client: AsyncClient, connect: Connect
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    async with connect(token["secret"]) as client:
        listed = await client.list_tools()
    names = {tool.name for tool in listed.tools}
    assert names == READ_TOOLS
    search = next(tool for tool in listed.tools if tool.name == "search")
    assert search.annotations is not None and search.annotations.read_only_hint is True
    assert search.input_schema["required"] == ["query"]
    assert search.input_schema.get("additionalProperties") is False


async def test_the_modern_protocol_works_without_a_session(
    owner: AsyncClient, member_client: AsyncClient, connect: Connect
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    async with connect(token["secret"], mode="auto") as client:
        listed = await client.list_tools()
        result = await client.call_tool("list_tree", {})
    assert {tool.name for tool in listed.tools} == READ_TOOLS
    assert not result.is_error


async def test_every_request_answers_on_its_own_without_a_session(
    owner: AsyncClient, member_client: AsyncClient, mcp_http: httpx2.AsyncClient
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    auth = {"Authorization": f"Bearer {token['secret']}"}
    opened = await mcp_http.post(URL, json=INITIALIZE, headers=auth)
    assert opened.status_code == 200, opened.text
    assert opened.headers["content-type"].startswith("application/json")
    assert "mcp-session-id" not in opened.headers
    assert "tools" in opened.json()["result"]["capabilities"]
    assert "resources" not in opened.json()["result"]["capabilities"]
    # No initialize needed on this request: nothing was kept from the one before.
    listed = await mcp_http.post(URL, json=rpc("tools/list", id_=2), headers=auth)
    assert listed.status_code == 200, listed.text
    assert {t["name"] for t in listed.json()["result"]["tools"]} == READ_TOOLS


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_no_server_streams_and_no_sessions_to_end(
    method: str, owner: AsyncClient, member_client: AsyncClient, mcp_http: httpx2.AsyncClient
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    r = await mcp_http.request(method, URL, headers={"Authorization": f"Bearer {token['secret']}"})
    assert r.status_code == 405
    assert r.headers["allow"] == "POST"


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer herd_pat_unknown", "Bearer "],
)
async def test_without_a_valid_token_the_same_401_in_the_mcp_form(
    authorization: str | None, mcp_http: httpx2.AsyncClient
) -> None:
    headers = {"Authorization": authorization} if authorization is not None else {}
    r = await mcp_http.post(URL, json=INITIALIZE, headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == 'Bearer realm="to-herd-cats-ai", error="invalid_token"'
    body = r.json()
    assert body["jsonrpc"] == "2.0" and body["id"] is None
    assert body["error"]["data"]["code"] == "token.invalid"
    assert len(body["error"]["data"]["trace_id"]) == 32
    assert set(body["error"]) == {"code", "message", "data"}


async def test_revoked_and_switched_off_answer_like_unknown(
    owner: AsyncClient, member_client: AsyncClient, mcp_http: httpx2.AsyncClient
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    auth = {"Authorization": f"Bearer {token['secret']}"}
    assert (await mcp_http.post(URL, json=INITIALIZE, headers=auth)).status_code == 200
    unknown = await mcp_http.post(URL, json=INITIALIZE, headers={"Authorization": "Bearer x"})
    await mcp_on(owner, enabled=False)
    off = await mcp_http.post(URL, json=INITIALIZE, headers=auth)
    await mcp_on(owner)
    assert (await member_client.delete(f"/api/tokens/{token['id']}")).status_code == 204
    revoked = await mcp_http.post(URL, json=INITIALIZE, headers=auth)
    for r in (off, revoked):
        assert r.status_code == 401
        assert r.json()["error"]["data"]["code"] == "token.invalid"
        assert r.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_a_session_cookie_is_no_token(
    owner: AsyncClient, member_client: AsyncClient, mcp_app: object
) -> None:
    """The browser's session cookie opens nothing at `/mcp`."""
    await mcp_on(owner)
    r = await member_client.post("/mcp", json=INITIALIZE)
    assert r.status_code == 401


@pytest.mark.parametrize("origin", ["https://evil.example", "http://test", "null"])
async def test_any_origin_is_refused_before_the_token(
    origin: str, owner: AsyncClient, member_client: AsyncClient, mcp_http: httpx2.AsyncClient
) -> None:
    """No browser may call `/mcp` (DNS rebinding, a page with a stolen token): a
    request that carries an `Origin` is refused, valid token or not."""
    await mcp_on(owner)
    token = await new_token(member_client)
    headers = {"Origin": origin, "Authorization": f"Bearer {token['secret']}"}
    r = await mcp_http.post(URL, json=INITIALIZE, headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["data"]["code"] == "mcp.origin_refused"
    assert "access-control-allow-origin" not in r.headers


async def test_past_the_rate_limit_429_in_the_mcp_form(
    owner: AsyncClient,
    member_client: AsyncClient,
    mcp_http: httpx2.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "mcp_rate_per_minute", 2)
    await mcp_on(owner)
    token = await new_token(member_client)
    auth = {"Authorization": f"Bearer {token['secret']}"}
    for _ in range(2):
        assert (await mcp_http.post(URL, json=INITIALIZE, headers=auth)).status_code == 200
    r = await mcp_http.post(URL, json=INITIALIZE, headers=auth)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "60"
    assert r.json()["error"]["data"]["code"] == "mcp.rate_limited"


async def test_an_unknown_tool_is_a_protocol_error(
    owner: AsyncClient, member_client: AsyncClient, mcp_http: httpx2.AsyncClient
) -> None:
    """Tools of the catalog that need a run (or a person's release) are not there."""
    await mcp_on(owner)
    token = await new_token(member_client)
    auth = {"Authorization": f"Bearer {token['secret']}"}
    for name in ("submit_result", "ask_user", "update_memory", "nope"):
        call = rpc("tools/call", {"name": name, "arguments": {}})
        r = await mcp_http.post(URL, json=call, headers=auth)
        assert r.status_code == 200
        assert r.json()["error"]["code"] == -32602, name


async def test_invalid_arguments_are_a_tool_error(
    owner: AsyncClient, member_client: AsyncClient, connect: Connect
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    async with connect(token["secret"]) as client:
        result = await client.call_tool("read_page", {"page_id": "not-a-uuid", "more": 1})
    assert result.is_error
    assert text_of(result).startswith("Invalid arguments")
    assert "not-a-uuid" not in text_of(result)


async def test_an_oversized_request_is_refused(
    owner: AsyncClient,
    member_client: AsyncClient,
    mcp_http: httpx2.AsyncClient,
    session: AsyncSession,
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    auth = {"Authorization": f"Bearer {token['secret']}"}
    big = rpc("tools/call", {"name": "search", "arguments": {"query": "x" * 2_000_000}})
    r = await mcp_http.post(URL, json=big, headers=auth)
    assert r.status_code == 413
