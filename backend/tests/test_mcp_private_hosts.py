"""External MCP servers inside the company network (M8 Task 7 ruling): the stub stands
for an in-house server at a private address (127.0.0.1, with no extra allowance in the
test network). Only a name or network the operator lists in `HERD_MCP_ALLOWED_HOSTS`
is reached; anything else stays refused, also a listed name that turns to a metadata
address, and a listed host is dialled past the operator's egress proxy."""

import ssl
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from app.core import egress
from app.core.config import get_settings
from app.core.egress import Network
from tests.factories_dms import People
from tests.factories_mcp import SERVERS
from tests.support.mcp_stub import McpStub


def _private_network(stub: McpStub, answers: dict[str, list[str]]) -> Network:
    async def resolve(host: str, port: int) -> list[str]:
        if host.endswith(".test"):
            return answers["now"]
        raise OSError("unknown name")

    return Network(
        resolver=resolve, ssl_context=ssl.create_default_context(cafile=str(stub.cert_path))
    )


@pytest.fixture
def answers(mcp_stub: McpStub, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    found = {"now": ["127.0.0.1"]}
    monkeypatch.setattr(egress, "_network", _private_network(mcp_stub, found))
    return found


def allow(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setattr(get_settings(), "mcp_allowed_hosts", raw)


async def create(admin: AsyncClient, url: str) -> Any:
    return await admin.post(SERVERS, json={"name": "GitLab intern", "url": url})


async def test_a_private_server_is_refused_unless_listed(
    ai_people: People,
    mcp_stub: McpStub,
    answers: dict[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made = await create(ai_people.admin, mcp_stub.url)
    assert made.status_code == 201, made.text
    assert made.json()["refresh"]["status"] == "blocked"
    allow(monkeypatch, "other.test, 10.0.0.0/8")  # neither the name nor its address
    refreshed = await ai_people.admin.post(f"{SERVERS}/{made.json()['id']}/refresh", json={})
    assert refreshed.json()["status"] == "blocked"
    assert mcp_stub.state.log == []  # never dialled
    allow(monkeypatch, "mcp.test")
    refreshed = await ai_people.admin.post(f"{SERVERS}/{made.json()['id']}/refresh", json={})
    assert refreshed.json()["status"] == "ok" and refreshed.json()["new"] == 2


async def test_a_listed_network_reaches_the_server(
    ai_people: People,
    mcp_stub: McpStub,
    answers: dict[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow(monkeypatch, "127.0.0.0/8")
    made = await create(ai_people.admin, mcp_stub.url)
    assert made.json()["refresh"]["status"] == "ok"


async def test_a_listed_name_that_turns_to_metadata_stays_refused(
    ai_people: People,
    mcp_stub: McpStub,
    answers: dict[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS rebinding against a listed name: every connection resolves anew and judges
    each answer."""
    allow(monkeypatch, "mcp.test")
    made = await create(ai_people.admin, mcp_stub.url)
    assert made.json()["refresh"]["status"] == "ok"
    mcp_stub.state.log.clear()
    answers["now"] = ["169.254.169.254"]
    tested = await ai_people.admin.post(f"{SERVERS}/{made.json()['id']}/test", json={})
    assert tested.json()["status"] == "blocked"
    answers["now"] = ["127.0.0.1", "169.254.169.254"]
    tested = await ai_people.admin.post(f"{SERVERS}/{made.json()['id']}/test", json={})
    assert tested.json()["status"] == "blocked"
    assert mcp_stub.state.log == []


async def test_literal_private_urls_follow_the_allowance(
    ai_people: People, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused = await create(ai_people.admin, "https://10.20.0.5/mcp")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "mcp_server.url_not_allowed"
    allow(monkeypatch, "10.20.0.0/16")
    for url in ("https://10.21.0.5/mcp", "https://169.254.169.254/mcp", "http://10.20.0.5/mcp"):
        r = await create(ai_people.admin, url)
        assert r.status_code == 422, url
    allowed = await create(ai_people.admin, "https://10.20.0.5/mcp")
    assert allowed.status_code == 201, allowed.text


async def test_a_listed_host_is_dialled_past_the_egress_proxy(
    ai_people: People,
    mcp_stub: McpStub,
    answers: dict[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An operator's proxy for the outside would not reach the in-house server; a
    host not listed still goes through it."""
    monkeypatch.setattr(get_settings(), "ai_egress_proxy", SecretStr("http://proxy.invalid:3128"))
    allow(monkeypatch, "mcp.test")
    made = await create(ai_people.admin, mcp_stub.url)
    assert made.json()["refresh"]["status"] == "ok"
    allow(monkeypatch, "")
    refreshed = await ai_people.admin.post(f"{SERVERS}/{made.json()['id']}/refresh", json={})
    assert refreshed.json()["status"] != "ok"
