"""The demo scripts' API helper waits out the write limit (J10) instead of failing."""

import httpx
import pytest

from scripts import demo_api


async def test_a_limited_write_is_sent_again_after_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        httpx.Response(429, headers={"Retry-After": "2"}, json={"error": {"code": "rate.limited"}}),
        httpx.Response(201, json={"id": "x"}),
    ]
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(demo_api.asyncio, "sleep", sleep)
    transport = httpx.MockTransport(lambda request: answers.pop(0))
    async with httpx.AsyncClient(transport=transport, base_url="http://demo") as client:
        assert await demo_api.call(client, "POST", "/api/things", {}) == {"id": "x"}
    assert slept == [2]


async def test_a_lasting_limit_fails_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    async def sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(demo_api.asyncio, "sleep", sleep)
    limited = httpx.Response(
        429, headers={"Retry-After": "1"}, json={"error": {"code": "rate.limited"}}
    )
    transport = httpx.MockTransport(lambda request: limited)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo") as client:
        with pytest.raises(demo_api.DemoFailed, match="429 rate.limited"):
            await demo_api.call(client, "POST", "/api/things", {})
