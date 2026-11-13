"""Checking a connection and listing its models against the OpenAI-protocol stub: the
request is shaped by the connection (param family, extra body, b-api route, no
streaming), the outcome is a state, and the key never comes back, however the
provider answers (the stub's error bodies echo the Authorization header)."""

import logging
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from app.core import egress
from app.core.config import get_settings
from app.core.egress import Network
from tests.support.openai_stub import OpenAIStub

BASE = "/api/ai/connections"
KEY = "sk-stub-ECHOED-KEY-0987654321"


@pytest.fixture(autouse=True)
def stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_AI_STUB_KEY", KEY)
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr("s" * 48))


async def local(client: AsyncClient, stub: OpenAIStub, **fields: Any) -> dict[str, Any]:
    body = {
        "name": "Lokal",
        "kind": "local",
        "base_url": stub.base_url,
        "models": ["m1", "m2"],
        "secret": {"env": "HERD_AI_STUB_KEY"},
        **fields,
    }
    response = await client.post(BASE, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def check(client: AsyncClient, connection: dict[str, Any], **body: Any) -> dict[str, Any]:
    response = await client.post(f"{BASE}/{connection['id']}/test", json=body)
    assert response.status_code == 200, response.text
    assert KEY not in response.text
    result: dict[str, Any] = response.json()
    return result


async def test_a_check_is_one_small_chat_call_with_the_key_in_the_header(
    owner: AsyncClient, openai_stub: OpenAIStub
) -> None:
    connection = await local(owner, openai_stub, extra_body={"reasoning_effort": "none"})
    result = await check(owner, connection)
    assert result["status"] == "ok" and result["model"] == "m1"
    assert result["duration_ms"] >= 0
    [request] = openai_stub.state.log
    assert request.path == "/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.body["model"] == "m1" and request.body["stream"] is False
    assert request.body["max_tokens"] == 16 and "max_completion_tokens" not in request.body
    assert request.body["reasoning_effort"] == "none"
    assert (await check(owner, connection, model="m2"))["model"] == "m2"


async def test_openai_uses_max_completion_tokens_over_tls(
    owner: AsyncClient, openai_tls_stub: OpenAIStub, stub_egress: Network
) -> None:
    response = await owner.post(
        BASE,
        json={"name": "OpenAI", "base_url": openai_tls_stub.base_url, "secret": {"value": KEY}},
    )
    result = await check(owner, response.json())
    assert result == {**result, "status": "ok", "model": "gpt-6-luna"}
    [request] = openai_tls_stub.state.log
    assert request.body["max_completion_tokens"] == 16 and "max_tokens" not in request.body
    assert request.headers["authorization"] == f"Bearer {KEY}"


async def test_b_api_sends_the_route_name_and_never_streams(
    owner: AsyncClient, openai_tls_stub: OpenAIStub, stub_egress: Network
) -> None:
    response = await owner.post(
        BASE,
        json={
            "name": "B",
            "kind": "b_api",
            "base_url": openai_tls_stub.base_url,
            "models": ["route-chat-de"],
            "secret": {"env": "HERD_AI_STUB_KEY"},
        },
    )
    assert response.json()["streaming"] is False
    assert (await check(owner, response.json()))["status"] == "ok"
    [request] = openai_tls_stub.state.log
    assert request.body["model"] == "route-chat-de" and request.body["stream"] is False


async def test_embedding_connections_are_checked_with_an_embedding(
    owner: AsyncClient, openai_stub: OpenAIStub
) -> None:
    connection = await local(owner, openai_stub, purpose="embedding", models=["emb"])
    assert (await check(owner, connection))["status"] == "ok"
    assert [r.path for r in openai_stub.state.log] == ["/v1/embeddings"]


@pytest.mark.parametrize(
    ("status", "state"),
    [
        (401, "unauthorized"),
        (402, "payment_required"),
        (403, "forbidden"),
        (404, "not_found"),
        (429, "rate_limited"),
        (500, "provider_error"),
        (503, "provider_error"),
    ],
)
async def test_provider_refusals_become_states_without_the_providers_words(
    owner: AsyncClient,
    openai_stub: OpenAIStub,
    capsys: pytest.CaptureFixture[str],
    status: int,
    state: str,
) -> None:
    connection = await local(owner, openai_stub)
    openai_stub.state.failures.append(status)
    result = await check(owner, connection)
    assert result["status"] == state
    assert len(openai_stub.state.log) == 1  # no retry
    out = capsys.readouterr()
    assert KEY not in out.out + out.err and "provider says no" not in out.out


async def test_slow_unreachable_odd_and_redirecting_providers(
    owner: AsyncClient, openai_stub: OpenAIStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = await local(owner, openai_stub)
    monkeypatch.setattr(get_settings(), "ai_check_timeout_seconds", 0.3)
    openai_stub.state.delay = 1.0
    assert (await check(owner, connection))["status"] == "timeout"
    openai_stub.state.delay = 0
    openai_stub.state.invalid_json = True
    assert (await check(owner, connection))["status"] == "invalid_response"
    openai_stub.state.invalid_json = False
    openai_stub.state.redirect_to = "http://169.254.169.254/latest/meta-data"
    assert (await check(owner, connection))["status"] == "redirect"
    gone = await local(owner, openai_stub, name="Weg", base_url="http://127.0.0.1:9/v1")
    assert (await check(owner, gone))["status"] == "unreachable"


async def test_the_guard_blocks_before_any_byte_is_sent(
    owner: AsyncClient,
    openai_tls_stub: OpenAIStub,
    stub_network: Network,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stub's name resolves to 127.0.0.1, which an external kind may not dial."""
    without_allowance = Network(
        resolver=stub_network.resolver, ssl_context=stub_network.ssl_context
    )
    monkeypatch.setattr(egress, "_network", without_allowance)
    response = await owner.post(
        BASE,
        json={
            "name": "X",
            "kind": "openai_compatible",
            "base_url": openai_tls_stub.base_url,
            "models": ["m"],
            "secret": {"env": "HERD_AI_STUB_KEY"},
        },
    )
    assert (await check(owner, response.json()))["status"] == "blocked"
    assert openai_tls_stub.state.log == []


async def test_missing_secrets_and_models_are_named(
    owner: AsyncClient, openai_stub: OpenAIStub
) -> None:
    unset = await local(owner, openai_stub, secret={"env": "HERD_AI_NOT_SET"})
    assert (await check(owner, unset))["status"] == "secret_unavailable"
    empty = await local(owner, openai_stub, name="Leer", models=[])
    assert (await check(owner, empty)) == {"status": "no_model", "model": None, "duration_ms": 0}
    assert openai_stub.state.log == []


async def test_nothing_leaks_at_debug_level_either(
    owner: AsyncClient, openai_stub: OpenAIStub, capsys: pytest.CaptureFixture[str]
) -> None:
    connection = await local(owner, openai_stub, secret={"value": KEY})
    root = logging.getLogger()
    level = root.level
    root.setLevel(logging.DEBUG)
    try:
        for failure in (401, 500):
            openai_stub.state.failures.append(failure)
            await check(owner, connection)
        openai_stub.state.delay = 0
        await check(owner, connection)
        response = await owner.post(f"{BASE}/{connection['id']}/models", json={"version": 1})
    finally:
        root.setLevel(level)
    out = capsys.readouterr()
    assert response.status_code == 200
    assert KEY not in out.out + out.err
    assert '"ai.provider_call"' in out.out  # the calls are logged, by status only


async def test_models_are_read_from_the_provider(
    owner: AsyncClient, openai_stub: OpenAIStub
) -> None:
    connection = await local(owner, openai_stub, models=["gpt-6-luna"])
    openai_stub.state.models = ["zeta", "alpha", "gpt-6-luna", "alpha"]
    path = f"{BASE}/{connection['id']}/models"
    stale = await owner.post(path, json={"version": 7})
    assert stale.status_code == 409 and openai_stub.state.log == []
    response = await owner.post(path, json={"version": 1})
    assert response.status_code == 200, response.text
    assert response.json()["models"] == ["gpt-6-luna", "alpha", "zeta"]
    assert response.json()["version"] == 2
    [request] = openai_stub.state.log
    assert request.method == "GET" and request.path == "/v1/models"


async def test_a_failed_listing_names_its_state_and_changes_nothing(
    owner: AsyncClient, openai_stub: OpenAIStub
) -> None:
    connection = await local(owner, openai_stub)
    openai_stub.state.failures.append(401)
    response = await owner.post(f"{BASE}/{connection['id']}/models", json={"version": 1})
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "ai.provider_failed" and error["details"] == {"status": "unauthorized"}
    assert KEY not in response.text and "provider says no" not in response.text
    again = await owner.get(f"{BASE}/{connection['id']}")
    assert again.json()["version"] == 1 and again.json()["models"] == ["m1", "m2"]
