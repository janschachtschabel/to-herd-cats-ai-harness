"""The WebSocket relay `/collab/{page_id}` (plan M2 task 9): the public app checks
Origin, session and `page.edit` like the REST API, then passes frames both ways to
the collab process, which gets a grant for the page and generation instead of the
session cookie (plan M9 task 6). Runs the real app on a real port (uvicorn) against a stand-in
collab process (a local WebSocket server) and committed data (tests/real_db.py)."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
import uvicorn
from pydantic import SecretStr
from websockets.asyncio.client import connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.core.config import get_settings
from app.core.models_base import utcnow
from app.modules.wiki import collab_grants
from app.modules.wiki.collab_grants import PREFIX
from app.web.public import create_public_app
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

TOKEN = "p" * 40


@dataclass
class Upstream:
    """The stand-in collab process: echoes frames, records each handshake."""

    url: str = ""
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    closed: int = 0  # upstream connections that ended


@pytest.fixture
async def upstream(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Upstream]:
    seen = Upstream()

    async def handler(ws: ServerConnection) -> None:
        assert ws.request is not None
        seen.requests.append((ws.request.path, dict(ws.request.headers.raw_items())))
        try:
            async for message in ws:
                if message == "close-4409":
                    await ws.close(4409, "generation_ended")
                    return
                await ws.send(message)
        finally:
            seen.closed += 1

    # As large as the collab process takes (its WebSocket server's maxPayload).
    async with serve(handler, "127.0.0.1", 0, max_size=None) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        seen.url = f"ws://127.0.0.1:{port}"
        monkeypatch.setattr(get_settings(), "collab_url", seen.url)
        yield seen


@pytest.fixture
async def public_url(real_db: RealDb, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    """The public app served by uvicorn on a free port; its ws:// base URL."""
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    monkeypatch.setattr(get_settings(), "public_url", "http://wiki.example")
    from app.web.collab_proxy import MAX_MESSAGE_BYTES

    config = uvicorn.Config(
        create_public_app(),
        host="127.0.0.1",
        port=0,
        log_config=None,
        lifespan="off",
        ws_max_size=MAX_MESSAGE_BYTES,  # as app.launch serves it
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


async def test_relays_a_live_state_as_large_as_collab_allows(
    public_url: str, setup: Setup, upstream: Upstream
) -> None:
    """Review M2 U3: the relay capped a message at 1 MiB while the collab process sends a
    state of up to 5 MiB in one message; a table page of 1 MiB of state never opened."""
    from app.modules.wiki.collab_models import MAX_YDOC_BYTES

    headers = {"Origin": "http://wiki.example", "Cookie": setup.cookie}
    state = bytes(range(256)) * (MAX_YDOC_BYTES // 256)  # the whole state in one message
    async with connect(
        _url(public_url, setup.page), additional_headers=headers, max_size=None
    ) as ws:
        await ws.send(state)
        assert await ws.recv() == state


def test_the_relay_passes_what_the_collab_process_allows() -> None:
    """One limit (review M2 U3): the collab process's state cap and message cap
    (collab/size.mjs) are the API's state cap and the relay's message cap."""
    import re
    from pathlib import Path

    from app.modules.wiki.collab_models import MAX_YDOC_BYTES
    from app.web.collab_proxy import MAX_MESSAGE_BYTES, MESSAGE_ENVELOPE_BYTES

    size = (Path(__file__).parents[2] / "collab" / "size.mjs").read_text()

    def constant(name: str) -> int:
        match = re.search(rf"export const {name} = ([0-9_ *]+);", size)
        assert match, name
        value = 1
        for factor in match.group(1).replace("_", "").split("*"):
            value *= int(factor)
        return value

    assert constant("MAX_STATE_BYTES") == MAX_YDOC_BYTES
    assert constant("MESSAGE_ENVELOPE_BYTES") == MESSAGE_ENVELOPE_BYTES
    assert MAX_MESSAGE_BYTES == MAX_YDOC_BYTES + MESSAGE_ENVELOPE_BYTES


async def test_the_relay_sends_no_cookie_upstream(
    public_url: str, setup: Setup, upstream: Upstream, real_db: RealDb
) -> None:
    """Plan M9 decision 16 (R14): the collab process gets a grant for exactly this
    page and generation, never the session cookie or anything else of the browser's."""
    headers = {
        "Origin": "http://wiki.example",
        "Cookie": f"other=secret; {setup.cookie}",
        "Authorization": "Bearer nope",
    }
    for _ in range(2):  # a grant per connection
        async with connect(_url(public_url, setup.page, 0), additional_headers=headers) as ws:
            await ws.send("ping")
            await ws.recv()
    grants = []
    for path, forwarded in upstream.requests:
        assert path == f"/collab/{setup.page['id']}?generation=0"
        assert set(forwarded) == {
            "Host",
            "Upgrade",
            "Connection",
            "Sec-WebSocket-Key",
            "Sec-WebSocket-Version",
            "User-Agent",
            "Authorization",
            "Origin",
            "X-Forwarded-Host",
        }
        assert forwarded["Origin"] == "http://wiki.example"
        assert forwarded["X-Forwarded-Host"].startswith("127.0.0.1:")
        scheme, grant = forwarded["Authorization"].split(" ")
        assert scheme == "Bearer" and grant.startswith(PREFIX)
        cookie_value = setup.cookie.split("=", 1)[1]
        assert cookie_value not in str(forwarded)
        grants.append(grant)
    assert len(set(grants)) == 2
    page_id = UUID(setup.page["id"])
    async with real_db.database.session_factory() as session:
        for grant in grants:
            ref = await collab_grants.resolve(
                session, grant, page_id=page_id, generation=0, now=utcnow()
            )
            assert ref is not None and ref.session_id is not None
            for other_page, generation in ((page_id, 1), (uuid4(), 0)):
                found = await collab_grants.resolve(
                    session, grant, page_id=other_page, generation=generation, now=utcnow()
                )
                assert found is None


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


async def test_a_browser_gone_during_the_handshake_frees_the_upstream_at_once(
    public_url: str, setup: Setup, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review M2 U11: a browser that aborted while the relay checked and dialled left
    the upstream connection open until the collab process's 10 s handshake timeout,
    holding one of the login session's slots there."""
    import socket
    from urllib.parse import urlsplit

    from app.web import collab_proxy

    real = collab_proxy._dial

    async def slow(*args: Any) -> Any:
        await asyncio.sleep(0.3)  # the browser is gone by now
        return await real(*args)

    monkeypatch.setattr(collab_proxy, "_dial", slow)
    url = urlsplit(_url(public_url, setup.page))
    for _ in range(3):
        raw = socket.create_connection((url.hostname, url.port))
        raw.sendall(
            (
                f"GET {url.path}?{url.query} HTTP/1.1\r\nHost: {url.netloc}\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n"
                f"Origin: http://wiki.example\r\nCookie: {setup.cookie}\r\n\r\n"
            ).encode()
        )
        await asyncio.sleep(0.05)
        raw.close()  # aborted before the relay answers
    for _ in range(100):  # 2 s, far below the collab process's 10 s
        if len(upstream.requests) == 3 and upstream.closed == 3:
            break
        await asyncio.sleep(0.02)
    assert len(upstream.requests) == 3
    assert upstream.closed == 3, "every upstream connection of an aborted browser is closed"


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
