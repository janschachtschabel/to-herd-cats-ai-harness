"""One request body limit for the whole app (`HERD_MAX_BODY_BYTES`, default 1 MiB).

A larger body is answered with 413 in the error shape before anything buffers it: at
once from `Content-Length`, and while reading for a body without one (chunked). It
holds for every path, before routing, CSRF and authentication.
"""

import json
from typing import Any

from httpx import ASGITransport, AsyncClient
from starlette.types import Message

from app.core.config import Settings
from app.web.public import create_public_app

LIMIT = 64 * 1024
CHUNK = 16 * 1024


def _app(limit: int = LIMIT) -> Any:
    return create_public_app(Settings(environment="test", max_body_bytes=limit))


def _assert_413(status: int, body: bytes) -> None:
    assert status == 413
    error = json.loads(body)["error"]
    assert error["code"] == "request.too_large" and len(error["trace_id"]) == 32


def test_the_default_limit_is_one_mebibyte() -> None:
    assert Settings().max_body_bytes == 1024 * 1024


async def test_a_declared_length_over_the_limit_is_refused_unread() -> None:
    reads = 0

    async def receive() -> Message:
        nonlocal reads
        reads += 1
        return {"type": "http.request", "body": b"x" * CHUNK, "more_body": True}

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/auth/login",
        "raw_path": b"/api/auth/login",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(LIMIT + 1).encode()),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    await _app()(scope, receive, send)
    assert reads == 0
    _assert_413(sent[0]["status"], b"".join(m.get("body", b"") for m in sent[1:]))


async def test_a_streamed_body_is_cut_off_at_the_limit() -> None:
    """No Content-Length: the bytes are counted as they arrive; reading stops at the
    first chunk over the limit, whatever follows."""
    reads = 0

    async def receive() -> Message:
        nonlocal reads
        reads += 1
        return {"type": "http.request", "body": b"x" * CHUNK, "more_body": True}

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/auth/login",
        "raw_path": b"/api/auth/login",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"x-requested-with", b"herd")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    await _app()(scope, receive, send)
    assert reads == LIMIT // CHUNK + 1
    _assert_413(sent[0]["status"], b"".join(m.get("body", b"") for m in sent[1:]))


async def test_every_path_and_caller_is_limited() -> None:
    body = b"x" * (LIMIT + 1)
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as anonymous:
        for path in ("/api/auth/login", "/api/spaces", "/api/nope", "/somewhere"):
            response = await anonymous.post(
                path, content=body, headers={"Content-Type": "application/json"}
            )
            _assert_413(response.status_code, response.content)
        response = await anonymous.post("/api/auth/login", content=body)  # no JSON
        _assert_413(response.status_code, response.content)
        assert response.headers["x-content-type-options"] == "nosniff"


async def test_a_body_within_the_limit_reaches_the_route() -> None:
    password = "x" * (LIMIT - 100)
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "a@example.com", "password": password},
            headers={"X-Requested-With": "herd"},
        )
    assert response.status_code == 422  # parsed and validated: the password is too long
    assert "password" in response.json()["error"]["message"]


async def test_file_routes_have_a_limit_of_their_own() -> None:
    """Uploads take bodies up to `HERD_ATTACHMENT_MAX_BYTES`, only on their route and
    method; above that they are refused like any other body, before authentication."""
    app = create_public_app(
        Settings(environment="test", max_body_bytes=LIMIT, attachment_max_bytes=2 * LIMIT)
    )
    upload = "/api/pages/0190f0f0-0000-7000-8000-000000000000/attachments"
    transport = ASGITransport(app=app)
    headers = {"X-Requested-With": "herd"}
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as anonymous:
        within = await anonymous.post(upload, content=b"x" * (LIMIT + 1))
        assert within.status_code == 401  # through the limit, stopped by authentication
        over = await anonymous.post(upload, content=b"x" * (2 * LIMIT + 1))
        _assert_413(over.status_code, over.content)

        async def streamed() -> Any:
            for _ in range(3):
                yield b"x" * LIMIT

        # Without a length nothing is refused unread; an anonymous body is never read.
        chunked = await anonymous.post(upload, content=streamed())
        assert chunked.status_code == 401
        for method, path in (("PUT", upload), ("POST", upload + "/x"), ("POST", "/api/spaces")):
            other = await anonymous.request(method, path, content=b"x" * (LIMIT + 1))
            _assert_413(other.status_code, other.content)
