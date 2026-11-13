"""Text with a NUL character (PostgreSQL rejects 0x00) is a caller error: 422, never 500,
whichever way it arrives: JSON body, query string, path, or inside a cursor."""

import base64
import json
import uuid

from httpx import AsyncClient

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
