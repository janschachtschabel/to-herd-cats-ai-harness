"""The WebSocket relay `/collab/{page_id}` (plan M2 task 9): the public app checks
Origin, session and `page.edit` like the REST API, then passes frames both ways to
the collab process. Runs the real app on a real port (uvicorn) against a stand-in
collab process (a local WebSocket server) and committed data (tests/real_db.py)."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
import uvicorn
from pydantic import SecretStr
from websockets.asyncio.client import connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.core.config import get_settings
from app.web.public import create_public_app
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

TOKEN = "p" * 40


@dataclass
class Upstream:
    """The stand-in collab process: echoes frames, records each handshake."""

    url: str = ""
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)


@pytest.fixture
async def upstream(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Upstream]:
    seen = Upstream()

    async def handler(ws: ServerConnection) -> None:
        assert ws.request is not None
        seen.requests.append((ws.request.path, dict(ws.request.headers.raw_items())))
        async for message in ws:
            if message == "close-4409":
                await ws.close(4409, "generation_ended")
                return
            await ws.send(message)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        seen.url = f"ws://127.0.0.1:{port}"
        monkeypatch.setattr(get_settings(), "collab_url", seen.url)
        yield seen


@pytest.fixture
async def public_url(real_db: RealDb, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    """The public app served by uvicorn on a free port; its ws:// base URL."""
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    monkeypatch.setattr(get_settings(), "public_url", "http://wiki.example")
    config = uvicorn.Config(
        create_public_app(), host="127.0.0.1", port=0, log_config=None, lifespan="off"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 -- uvicorn offers no event for it
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"ws://127.0.0.1:{port}"
    server.should_exit = True
    await task


@dataclass
class Setup:
    cookie: str
    page: dict[str, Any]
    member_cookie: str


@pytest.fixture
async def setup(real_db: RealDb, make_real_client: MakeRealClient) -> Setup:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    member = await make_real_client()
    me = await login(member, real_db.member_email)
    space = (await owner.post("/api/spaces", json={"name": "Live", "kind": "team"})).json()
    page = (await owner.post(f"/api/spaces/{space['id']}/pages", json={"title": "S"})).json()
    r = await owner.post(f"/api/pages/{page['id']}/publish", json={"version": page["version"]})
    r = await owner.put(
        f"/api/spaces/{space['id']}/members",
        json={"member_type": "user", "member_id": me["user"]["id"], "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    name = get_settings().session_cookie_name
    return Setup(f"{name}={owner.cookies.get(name)}", page, f"{name}={member.cookies.get(name)}")


def _url(base: str, page: dict[str, Any], generation: int = 0) -> str:
    return f"{base}/collab/{page['id']}?generation={generation}"


async def _refused(url: str, **headers: str) -> int:
    """The handshake itself is refused: its HTTP status."""
    with pytest.raises(InvalidStatus) as refused:
        async with connect(url, additional_headers=headers):
            pass
    return refused.value.response.status_code


async def _closed(url: str, **headers: str) -> tuple[int, str]:
    """Accepted and closed before a frame passes: the close code and reason (a browser
    cannot read a refused handshake's status, but it can read these)."""
    async with connect(url, additional_headers=headers) as ws:
        with pytest.raises(ConnectionClosed) as closed:
            await ws.recv()
    assert closed.value.rcvd is not None
    return closed.value.rcvd.code, closed.value.rcvd.reason


async def test_rejects_foreign_origin(public_url: str, setup: Setup, upstream: Upstream) -> None:
    url = _url(public_url, setup.page)
    assert await _refused(url, Cookie=setup.cookie, Origin="http://evil.example") == 403
    assert await _refused(url, Cookie=setup.cookie) == 403
    assert upstream.requests == []


async def test_checks_session_and_page_edit_like_the_api(
    public_url: str, setup: Setup, upstream: Upstream
) -> None:
    origin = "http://wiki.example"
    url = _url(public_url, setup.page)
    assert await _closed(url, Origin=origin) == (4401, "auth.required")
    assert await _closed(url, Origin=origin, Cookie="herd_session=nope") == (
        4401,
        "collab.session_invalid",
    )
    viewer = await _closed(url, Origin=origin, Cookie=setup.member_cookie)
    assert viewer == (4403, "auth.permission_denied")
    unknown = {"id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"}
    hidden = await _closed(_url(public_url, unknown), Origin=origin, Cookie=setup.cookie)
    assert hidden == (4404, "page.not_found")
    stale = _url(public_url, setup.page, generation=3)
    assert await _closed(stale, Origin=origin, Cookie=setup.cookie) == (
        4409,
        "collab.generation_ended",
    )
    bad = f"{public_url}/collab/{setup.page['id']}?generation=x"
    assert await _closed(bad, Origin=origin, Cookie=setup.cookie) == (
        4400,
        "collab.generation_invalid",
    )
    assert upstream.requests == []


async def test_relays_frames_both_ways(public_url: str, setup: Setup, upstream: Upstream) -> None:
    headers = {"Origin": "http://wiki.example", "Cookie": setup.cookie}
    async with connect(_url(public_url, setup.page), additional_headers=headers) as ws:
        await ws.send(b"\x00\x01binary")
        assert await ws.recv() == b"\x00\x01binary"
        await ws.send("text")
        assert await ws.recv() == "text"
        await ws.send("close-4409")
        with pytest.raises(ConnectionClosed) as closed:
            await ws.recv()
    assert closed.value.rcvd is not None
    assert (closed.value.rcvd.code, closed.value.rcvd.reason) == (4409, "generation_ended")


async def test_forwards_cookie_header(public_url: str, setup: Setup, upstream: Upstream) -> None:
    headers = {
        "Origin": "http://wiki.example",
        "Cookie": f"other=secret; {setup.cookie}",
        "Authorization": "Bearer nope",
    }
    async with connect(_url(public_url, setup.page, 0), additional_headers=headers) as ws:
        await ws.send("ping")
        await ws.recv()
    ((path, forwarded),) = upstream.requests
    assert path == f"/collab/{setup.page['id']}?generation=0"
    assert forwarded["Cookie"] == setup.cookie  # only the session cookie
    assert forwarded["Origin"] == "http://wiki.example"
    assert forwarded["X-Forwarded-Host"].startswith("127.0.0.1:")
    assert "Authorization" not in forwarded


async def test_live_editing_off_without_internal_token(
    public_url: str, setup: Setup, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "internal_token", None)
    url = _url(public_url, setup.page)
    closed = await _closed(url, Origin="http://wiki.example", Cookie=setup.cookie)
    assert closed == (4503, "collab.disabled")


async def test_collab_process_down_is_502(
    public_url: str, setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "collab_url", "ws://127.0.0.1:1")
    url = _url(public_url, setup.page)
    closed = await _closed(url, Origin="http://wiki.example", Cookie=setup.cookie)
    assert closed == (4502, "collab.unavailable")


async def test_a_handshake_that_takes_too_long_is_closed(
    public_url: str, setup: Setup, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review M2 R7: checking and dialling the collab process together take at most
    HANDSHAKE_TIMEOUT_SECONDS; a socket stuck there does not stay open."""
    from app.web import collab_proxy

    real = collab_proxy._authorize

    async def slow(*args: Any) -> Any:
        await asyncio.sleep(1.0)
        return await real(*args)

    monkeypatch.setattr(collab_proxy, "HANDSHAKE_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(collab_proxy, "_authorize", slow)
    url = _url(public_url, setup.page)
    closed = await _closed(url, Origin="http://wiki.example", Cookie=setup.cookie)
    assert closed == (4504, "collab.timeout")
    assert upstream.requests == []


async def test_connections_are_counted(public_url: str, setup: Setup, upstream: Upstream) -> None:
    from app.core.metrics import COLLAB_CONNECTIONS

    before = COLLAB_CONNECTIONS._value.get()
    headers = {"Origin": "http://wiki.example", "Cookie": setup.cookie}
    async with connect(_url(public_url, setup.page), additional_headers=headers) as ws:
        await ws.send("x")
        await ws.recv()
        assert COLLAB_CONNECTIONS._value.get() == before + 1
    for _ in range(100):
        if COLLAB_CONNECTIONS._value.get() == before:
            break
        await asyncio.sleep(0.01)
    assert COLLAB_CONNECTIONS._value.get() == before


def test_origin_without_public_url_must_match_the_host() -> None:
    from app.web.collab_proxy import origin_allowed

    assert origin_allowed("https://wiki.example", "wiki.example", None)
    assert origin_allowed("http://127.0.0.1:8080", "127.0.0.1:8080", None)
    assert not origin_allowed("https://evil.example", "wiki.example", None)
    assert not origin_allowed("https://wiki.example:8443", "wiki.example", None)
    assert not origin_allowed(None, "wiki.example", None)
    assert not origin_allowed("https://wiki.example", None, None)
    # With HERD_PUBLIC_URL, only its origin (scheme included).
    assert origin_allowed("https://wiki.example", "10.0.0.5:8080", "https://wiki.example/")
    assert not origin_allowed("http://wiki.example", "wiki.example", "https://wiki.example")


def test_public_url_must_be_an_http_origin() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    assert Settings(public_url="https://wiki.example").public_url == "https://wiki.example"
    for bad in ("wiki.example", "ftp://wiki.example", "https://"):
        with pytest.raises(ValidationError):
            Settings(public_url=bad)
