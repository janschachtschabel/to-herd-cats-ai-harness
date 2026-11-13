"""The internal collab API (plan M2 task 8): the collab process authenticates live
editors, loads and saves pages through it; generations end stale live sessions, and
every save checks again that each editor may still edit."""

import base64
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.modules.wiki.models import PageVersion
from app.web.internal import create_internal_app
from tests.conftest import session_override
from tests.factories_wiki import Wiki, new_page, publish

TOKEN = "t" * 40
HEADER = "X-Herd-Internal-Token"


@pytest.fixture
def internal_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    return TOKEN


@pytest.fixture
async def internal(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """The internal app on the test session, without the token header."""
    app = create_internal_app()
    app.dependency_overrides[get_session] = session_override(session)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://internal") as client:
        yield client


@pytest.fixture
async def collab(internal: AsyncClient, internal_token: str) -> AsyncClient:
    internal.headers[HEADER] = internal_token
    return internal


def _token(client: AsyncClient) -> str:
    token = client.cookies.get(get_settings().session_cookie_name)
    assert token
    return token


async def _auth(collab: AsyncClient, client: AsyncClient, page: dict[str, Any]) -> Any:
    return await collab.post(
        "/internal/collab/auth", json={"session_token": _token(client), "page_id": page["id"]}
    )


async def _session_id(collab: AsyncClient, client: AsyncClient, page: dict[str, Any]) -> str:
    r = await _auth(collab, client, page)
    assert r.status_code == 200, r.text
    session_id: str = r.json()["session_id"]
    return session_id


def _ydoc(data: bytes = b"\x01\x02state") -> str:
    return base64.b64encode(data).decode()


async def _put(
    collab: AsyncClient,
    page: dict[str, Any],
    sessions: list[str],
    *,
    generation: int = 0,
    content_md: str = "live",
    ydoc_b64: str | None = None,
    session_key: str = "doc-1",
) -> Any:
    return await collab.put(
        f"/internal/collab/pages/{page['id']}",
        json={
            "generation": generation,
            "ydoc_b64": ydoc_b64 or _ydoc(),
            "content_md": content_md,
            "editor_session_ids": sessions,
            "session_key": session_key,
        },
    )


async def _get(client: AsyncClient, page: dict[str, Any]) -> Any:
    r = await client.get(f"/api/pages/{page['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _error(r: Any, status: int, code: str) -> Any:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    return r.json()["error"]


async def test_internal_routes_need_token(
    internal: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {"session_token": "x", "page_id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"}
    monkeypatch.setattr(get_settings(), "internal_token", None)
    r = await internal.post("/internal/collab/auth", json=body, headers={HEADER: TOKEN})
    _error(r, 503, "internal.disabled")
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    for headers in ({}, {HEADER: "wrong"}, {HEADER: TOKEN[:-1]}, {HEADER: TOKEN + "x"}):
        r = await internal.post("/internal/collab/auth", json=body, headers=headers)
        _error(r, 401, "internal.unauthorized")
    r = await internal.post("/internal/collab/auth", json=body, headers={HEADER: TOKEN})
    _error(r, 401, "collab.session_invalid")
    # Probes and metrics need no token.
    for path in ("/health", "/metrics"):
        assert (await internal.get(path)).status_code == 200


def test_a_short_internal_token_is_refused() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(internal_token=SecretStr("short"))
    assert Settings(internal_token=SecretStr("")).internal_token is None


async def test_auth_answers_editor_and_denies_viewer_and_hidden_page(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Live"))
    r = await _auth(collab, wiki.editor, page)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"] == {"id": str(wiki.users["editor"].id), "name": "Wiki editor"}
    assert (body["generation"], body["can_edit"]) == (0, True)
    assert body["session_id"]
    _error(await _auth(collab, wiki.viewer, page), 403, "auth.permission_denied")
    _error(await _auth(collab, wiki.outsider, page), 404, "page.not_found")
    r = await collab.post(
        "/internal/collab/auth", json={"session_token": "nope", "page_id": page["id"]}
    )
    _error(r, 401, "collab.session_invalid")
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    _error(await _auth(collab, wiki.viewer, draft), 404, "page.not_found")
    r = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert r.status_code == 204
    _error(await _auth(collab, wiki.editor, page), 404, "page.not_found")


async def test_get_returns_content_and_ydoc_of_the_current_generation_only(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="# Start")
    sid = await _session_id(collab, wiki.editor, page)
    url = f"/internal/collab/pages/{page['id']}"
    r = await collab.get(url, params={"session_id": sid, "generation": 0})
    assert r.status_code == 200, r.text
    assert r.json() == {"generation": 0, "ydoc_b64": None, "content_md": "# Start", "title": "Live"}
    assert (await _put(collab, page, [sid], ydoc_b64=_ydoc(b"yjs"))).status_code == 200
    r = await collab.get(url, params={"session_id": sid, "generation": 0})
    assert r.json()["ydoc_b64"] == _ydoc(b"yjs") and r.json()["content_md"] == "live"
    # Saved in Markdown mode: a new generation, the old live state is not handed out.
    fresh = await _get(wiki.editor, page)
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "markdown", "version": fresh["version"]}
    )
    assert r.json()["collab_generation"] == 1
    r = await collab.get(url, params={"session_id": sid, "generation": 1})
    assert r.json() == {
        "generation": 1,
        "ydoc_b64": None,
        "content_md": "markdown",
        "title": "Live",
    }
    _error(
        await collab.get(url, params={"session_id": sid, "generation": 0}),
        409,
        "collab.generation_ended",
    )
    # A session loads only pages its person may edit.
    space = (await wiki.admin.post("/api/spaces", json={"name": "Fremd", "kind": "team"})).json()
    foreign = await new_page(wiki.admin, space["id"], "Fremd")
    r = await collab.get(f"/internal/collab/pages/{foreign['id']}", params={"session_id": sid})
    _error(r, 404, "page.not_found")
    published = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Offen"))
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={"member_type": "user", "member_id": str(wiki.users["editor"].id), "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    r = await collab.get(f"/internal/collab/pages/{published['id']}", params={"session_id": sid})
    _error(r, 403, "auth.permission_denied")
    r = await collab.get(url, params={"session_id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"})
    _error(r, 401, "collab.session_invalid")


async def test_put_with_old_generation_is_409_and_changes_nothing(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="alt")
    sid = await _session_id(collab, wiki.editor, page)
    restored = await wiki.editor.post(
        f"/api/pages/{page['id']}/versions/1/restore", json={"version": page["version"]}
    )
    assert restored.json()["collab_generation"] == 1
    before = await _get(wiki.editor, page)
    error = _error(await _put(collab, page, [sid], generation=0), 409, "collab.generation_ended")
    assert error["details"] == {"generation": 1}
    after = await _get(wiki.editor, page)
    assert (after["content_md"], after["version"]) == (before["content_md"], before["version"])
    r = await collab.get(
        f"/internal/collab/pages/{page['id']}", params={"session_id": sid, "generation": 1}
    )
    assert r.json()["ydoc_b64"] is None


async def test_markdown_save_ends_generation(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"title": "Neu", "version": page["version"]}
    )
    assert r.json()["collab_generation"] == 0  # the title is not part of the live document
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "b", "version": r.json()["version"]}
    )
    assert r.json()["collab_generation"] == 1
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "b", "version": r.json()["version"]}
    )
    assert r.json()["collab_generation"] == 1  # nothing changed, nothing ended


async def test_put_saves_without_ending_the_generation(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    sid = await _session_id(collab, wiki.editor, page)
    r = await _put(collab, page, [sid], content_md="# Live\n\nText")
    assert r.status_code == 200, r.text
    after = await _get(wiki.editor, page)
    assert (after["content_md"], after["collab_generation"]) == ("# Live\n\nText", 0)
    assert r.json() == {"generation": 0, "version": after["version"]}
    assert after["version"] == page["version"] + 1
    # A REST client still holding the old version gets the usual conflict.
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "x", "version": page["version"]}
    )
    _error(r, 409, "page.version_conflict")


async def test_put_with_revoked_editor_is_403_and_saves_nothing(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await _session_id(collab, wiki.editor, page)
    editor2 = await _session_id(collab, wiki.editor2, page)
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={
            "member_type": "user",
            "member_id": str(wiki.users["editor2"].id),
            "role": "viewer",
        },
    )
    assert r.status_code == 200, r.text
    error = _error(await _put(collab, page, [editor, editor2]), 403, "collab.editors_revoked")
    assert error["details"] == {
        "revoked_session_ids": [editor2],
        "revoked_user_ids": [str(wiki.users["editor2"].id)],
    }
    assert (await _get(wiki.editor, page))["content_md"] == "a"
    r = await collab.get(
        f"/internal/collab/pages/{page['id']}", params={"session_id": editor, "generation": 0}
    )
    assert r.json()["ydoc_b64"] is None
    assert (await _put(collab, page, [editor])).status_code == 200


async def test_ended_session_and_deactivated_user_are_revoked(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    editor = await _session_id(collab, wiki.editor, page)
    editor2 = await _session_id(collab, wiki.editor2, page)
    moderator = await _session_id(collab, wiki.moderator, page)
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    r = await wiki.admin.post(f"/api/admin/users/{wiki.users['editor2'].id}/deactivate")
    assert r.status_code == 204, r.text
    check = await collab.post(
        f"/internal/collab/pages/{page['id']}/check",
        json={"session_ids": [editor, editor2, moderator], "generation": 0},
    )
    assert check.status_code == 200, check.text
    assert check.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_session_ids": sorted([editor, editor2]),
        "revoked_user_ids": [],  # whose ended session it was, the collab process knows
    }
    r = await _put(collab, page, [moderator, editor])
    assert _error(r, 403, "collab.editors_revoked")["details"]["revoked_session_ids"] == [editor]
    unknown = "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"
    r = await _put(collab, page, [unknown])
    assert _error(r, 403, "collab.editors_revoked")["details"]["revoked_session_ids"] == [unknown]


async def test_check_reports_an_ended_generation(wiki: Wiki, collab: AsyncClient) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Live"))
    sid = await _session_id(collab, wiki.editor, page)
    url = f"/internal/collab/pages/{page['id']}/check"
    r = await collab.post(url, json={"session_ids": [sid], "generation": 0})
    assert r.json()["generation_ok"] is True
    moved = await wiki.editor.post(
        f"/api/pages/{page['id']}/move", json={"parent_id": None, "version": page["version"]}
    )
    assert moved.status_code == 200, moved.text
    r = await collab.post(url, json={"session_ids": [sid], "generation": 0})
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 1)
    await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": moved.json()["version"]}
    )
    r = await collab.post(url, json={"session_ids": [sid], "generation": 2})
    assert r.json()["generation_ok"] is False  # in the trash: no live session


async def test_put_creates_coalesced_collab_versions_per_author(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="v1")
    editor = await _session_id(collab, wiki.editor, page)
    editor2 = await _session_id(collab, wiki.editor2, page)
    for text in ("a", "ab", "abc"):
        assert (await _put(collab, page, [editor], content_md=text)).status_code == 200
    versions_url = f"/api/pages/{page['id']}/versions"
    items = (await wiki.editor.get(versions_url)).json()["items"]
    assert [(v["number"], v["source"], v["author"]["name"]) for v in items] == [
        (2, "collab", "Wiki editor"),
        (1, "human", "Wiki editor"),
    ]
    assert (await wiki.editor.get(f"{versions_url}/2")).json()["content_md"] == "abc"
    # Another author gets a version of their own; a save by both folds into the
    # newest version, which is one of theirs.
    assert (await _put(collab, page, [editor2], content_md="abcd")).status_code == 200
    assert (await _put(collab, page, [editor2, editor], content_md="abcde")).status_code == 200
    items = (await wiki.editor.get(versions_url)).json()["items"]
    assert [(v["number"], v["author"]["name"]) for v in items][:2] == [
        (3, "Wiki editor2"),
        (2, "Wiki editor"),
    ]
    assert (await wiki.editor.get(f"{versions_url}/3")).json()["content_md"] == "abcde"
    # After 60 s the same author starts a new version.
    await session.execute(
        update(PageVersion)
        .where(PageVersion.page_id == page["id"], PageVersion.number == 3)
        .values(created_at=PageVersion.created_at - timedelta(seconds=61))
    )
    assert (await _put(collab, page, [editor2], content_md="abcdef")).status_code == 200
    # Another live session (a new document) does not fold into the old one's version.
    assert (
        await _put(collab, page, [editor2], content_md="abcdefg", session_key="doc-2")
    ).status_code == 200
    numbers = [v["number"] for v in (await wiki.editor.get(versions_url)).json()["items"]]
    assert numbers == [5, 4, 3, 2, 1]


async def test_ydoc_over_5mb_is_413(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await _session_id(collab, wiki.editor, page)
    big = _ydoc(b"\x00" * (5 * 1024 * 1024 + 1))
    _error(await _put(collab, page, [sid], ydoc_b64=big), 413, "collab.state_too_large")
    ok = _ydoc(b"\x00" * (5 * 1024 * 1024))
    assert (await _put(collab, page, [sid], ydoc_b64=ok)).status_code == 200


async def test_put_refuses_bad_input(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await _session_id(collab, wiki.editor, page)
    r = await _put(collab, page, [sid], content_md="x" * 200_001)
    _error(r, 422, "validation_failed")
    _error(await _put(collab, page, [sid], ydoc_b64="!!notbase64"), 422, "collab.state_invalid")
    _error(await _put(collab, page, []), 422, "validation_failed")


async def test_saves_are_counted(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await _session_id(collab, wiki.editor, page)
    await _put(collab, page, [sid])
    await _put(collab, page, [sid], generation=7)
    text = (await collab.get("/metrics")).text
    assert 'herd_collab_saves_total{result="saved"}' in text
    assert 'herd_collab_saves_total{result="generation_ended"}' in text
