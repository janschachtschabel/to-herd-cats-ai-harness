"""The built frontend, served by the public app: index.html for every unknown path
outside /api, hashed assets cached forever, security headers, nothing outside
`static_dir`."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.web.public import create_public_app
from app.web.spa import CONTENT_SECURITY_POLICY

INDEX = "<!doctype html><title>Herd</title>"
SECRET = "root:x:0:0"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX)
    (root / "favicon.svg").write_text("<svg/>")
    (root / "assets" / "index-AbC123.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text(SECRET)
    (root / "assets" / "link.txt").symlink_to(tmp_path / "secret.txt")
    return root


@pytest.fixture
async def client_with_static(static_dir: Path) -> AsyncIterator[AsyncClient]:
    app = create_public_app(Settings(environment="test", static_dir=static_dir))
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def raw_get(client: AsyncClient, path: str) -> tuple[int, bytes]:
    """GET with the path exactly as given: httpx would normalise `..` away, a server
    decodes `%2f` to `/` before the app sees it (as `scope["path"]`)."""
    transport = client._transport
    assert isinstance(transport, ASGITransport)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    sent: list[dict[str, object]] = []
    requested, done = False, asyncio.Event()

    async def receive() -> dict[str, object]:
        # The request once; then the client stays until the response is complete.
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body"):
            done.set()

    await transport.app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return int(status), body


async def test_root_serves_index(client_with_static: AsyncClient) -> None:
    response = await client_with_static.get("/")
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")


async def test_unknown_path_serves_index(client_with_static: AsyncClient) -> None:
    for path in ("/spaces/0190-abc", "/admin/users", "/login?redirect=/spaces"):
        response = await client_with_static.get(path)
        assert response.status_code == 200, path
        assert response.text == INDEX


async def test_api_404_is_json_not_index(client_with_static: AsyncClient) -> None:
    for path in ("/api/nope", "/api", "/api/spaces/x/y/z"):
        response = await client_with_static.get(path)
        assert response.status_code == 404, path
        assert response.headers["content-type"] == "application/json"
        assert response.json()["error"]["code"] == "not_found"
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = await client_with_static.request(method, "/api/nope")
        assert response.status_code == 404, method
    # The API itself is unaffected.
    assert (await client_with_static.get("/api/openapi.json")).status_code == 200


async def test_spa_security_headers(client_with_static: AsyncClient) -> None:
    for path in ("/", "/spaces", "/assets/index-AbC123.js", "/favicon.svg"):
        headers = (await client_with_static.get(path)).headers
        assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY, path
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "same-origin"


def test_csp_starts_from_self_and_forbids_framing() -> None:
    directives = dict(
        d.strip().split(" ", 1) for d in CONTENT_SECURITY_POLICY.split(";") if d.strip()
    )
    assert directives["default-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"
    assert directives["base-uri"] == "'none'"
    assert directives["object-src"] == "'none'"
    assert directives["form-action"] == "'self'"
    assert "script-src" not in directives  # scripts: 'self' only, never inline
    assert "*" not in CONTENT_SECURITY_POLICY
    assert "unsafe-eval" not in CONTENT_SECURITY_POLICY


async def test_hashed_assets_are_immutable_and_index_is_revalidated(
    client_with_static: AsyncClient,
) -> None:
    asset = await client_with_static.get("/assets/index-AbC123.js")
    assert asset.status_code == 200
    assert asset.text == "console.log(1)"
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "javascript" in asset.headers["content-type"]
    for path in ("/", "/index.html", "/spaces", "/favicon.svg"):
        assert (await client_with_static.get(path)).headers["cache-control"] == "no-cache", path


async def test_missing_asset_is_404_not_index(client_with_static: AsyncClient) -> None:
    # A chunk from an older build: answering with index.html would hide the failure.
    response = await client_with_static.get("/assets/index-Old999.js")
    assert response.status_code == 404
    assert response.text != INDEX


async def test_head_is_answered(client_with_static: AsyncClient) -> None:
    response = await client_with_static.head("/spaces")
    assert response.status_code == 200
    assert response.content == b""


async def test_other_methods_are_refused(client_with_static: AsyncClient) -> None:
    response = await client_with_static.post("/spaces")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/../../etc/passwd",
        "/assets/../../secret.txt",
        "/assets/../../../etc/passwd",
        "/..\\secret.txt",
        "/assets/link.txt",  # a symlink pointing outside
        "/%2e%2e/secret.txt",
        "/\x00",
        "//etc/passwd",
    ],
)
async def test_nothing_outside_static_dir_is_read(
    client_with_static: AsyncClient, path: str
) -> None:
    status, body = await raw_get(client_with_static, path)
    assert SECRET.encode() not in body
    assert b"root:" not in body
    # 422: a NUL anywhere in the URL is refused before routing (core.nul_guard).
    assert status in ((422,) if "\x00" in path else (200, 404)), (path, status)
    if status == 200:
        assert body == INDEX.encode()


async def test_encoded_traversal_through_http_is_refused(client_with_static: AsyncClient) -> None:
    for path in ("/..%2f..%2fetc/passwd", "/..%2fsecret.txt", "/assets/..%2f..%2fsecret.txt"):
        response = await client_with_static.get(path)
        assert SECRET not in response.text, path
        assert "root:" not in response.text


def test_static_dir_without_index_fails_at_start(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="index.html"):
        create_public_app(Settings(environment="test", static_dir=tmp_path))


async def test_without_static_dir_nothing_is_served_outside_api(client: AsyncClient) -> None:
    response = await client.get("/spaces")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
