"""Text with a NUL character (PostgreSQL rejects 0x00) is a caller error: 422, never 500,
whichever way it arrives: JSON body, query string, path, or inside a cursor."""

import asyncio
import base64
import json
import time
import uuid

from httpx import AsyncClient
from starlette.types import Message, Receive, Scope, Send

from app.core import nul_guard
from app.core.nul_guard import NulGuardMiddleware

NUL_CODE = "validation_failed"


def _assert_422(response) -> None:
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == NUL_CODE


async def test_nul_in_a_json_body(owner: AsyncClient) -> None:
    _assert_422(await owner.post("/api/spaces", json={"name": "a\u0000b", "kind": "team"}))
    # Raw JSON with the escape anywhere, also in a key or nested.
    raw = b'{"kind": "team", "name": "x", "description": "\\u0000"}'
    _assert_422(
        await owner.post("/api/spaces", content=raw, headers={"Content-Type": "application/json"})
    )


async def test_an_escaped_backslash_before_u0000_is_not_a_nul(owner: AsyncClient) -> None:
    response = await owner.post("/api/spaces", json={"name": "a\\u0000b", "kind": "team"})
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "a\\u0000b"


async def test_nul_in_the_query_string(owner: AsyncClient) -> None:
    _assert_422(await owner.get("/api/directory?q=a%00b"))
    _assert_422(await owner.get("/api/directory", params={"q": "a\u0000b"}))


async def test_nul_in_the_path(owner: AsyncClient) -> None:
    _assert_422(await owner.get("/api/spaces/a%00b"))


async def test_nul_inside_a_cursor(owner: AsyncClient) -> None:
    raw = json.dumps(["a\u0000b", str(uuid.uuid4())]).encode()
    cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    _assert_422(await owner.get("/api/directory", params={"cursor": cursor}))


async def _through_the_guard(chunks: list[bytes]) -> tuple[int, int]:
    """Runs the guard alone over a JSON body in `chunks`: (status, bytes the app read)."""
    pending = list(chunks)
    seen = 0

    async def receive() -> Message:
        body = pending.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(pending)}

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal seen
        more = True
        while more:
            message = await receive()
            seen += len(message.get("body", b""))
            more = message.get("more_body", False)
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    statuses: list[int] = []

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
    }
    await NulGuardMiddleware(app)(scope, receive, send)
    return statuses[0], seen


async def test_the_guard_costs_linear_time_in_the_number_of_chunks() -> None:
    """4 MiB in 1 KiB chunks: copying the buffer per chunk would move ~8 GiB."""
    chunks = [b"[" + b" " * 1023] + [b" " * 1024] * 4094 + [b" " * 1023 + b"]"]
    started = time.perf_counter()
    assert await _through_the_guard(chunks) == (204, 4 * 1024 * 1024)
    assert time.perf_counter() - started < 0.5


async def test_a_nul_escape_split_across_chunks_is_found() -> None:
    assert (await _through_the_guard([b'{"a": "x\\u00', b'00"}']))[0] == 422
    assert (await _through_the_guard([b'{"a": "x\\\\u00', b'00"}']))[0] == 204


async def test_a_large_body_is_scanned_off_the_event_loop(monkeypatch) -> None:
    threads: list[str] = []
    real_to_thread = asyncio.to_thread

    async def spy(func, /, *args):  # type: ignore[no-untyped-def]
        threads.append(func.__name__)
        return await real_to_thread(func, *args)

    monkeypatch.setattr(nul_guard.asyncio, "to_thread", spy)
    small = [b'{"a": "' + b"x" * 100 + b'"}']
    assert await _through_the_guard(small) == (204, len(small[0]))
    assert threads == []
    large = [b'{"a": "' + b"x" * nul_guard.OFF_LOOP_BYTES + b'\\u0000"}']
    assert (await _through_the_guard(large))[0] == 422
    assert threads == ["contains_nul"]
