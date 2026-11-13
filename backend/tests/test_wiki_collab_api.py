"""The internal collab API (plan M2 task 8): the collab process authenticates live
editors, loads and saves pages through it; a Markdown save ends the live session's
generation. Revocation and ended generations: `test_wiki_collab_revocation.py`."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.wiki.models import PageVersion
from tests.factories_collab import (
    HEADER,
    TOKEN,
    collab_auth,
    expect_error,
    get_page,
    put_live,
    session_id_of,
    ydoc,
)
from tests.factories_wiki import Wiki, new_page, publish


async def test_internal_routes_need_token(
    internal: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {"session_token": "x", "page_id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"}
    monkeypatch.setattr(get_settings(), "internal_token", None)
    r = await internal.post("/internal/collab/auth", json=body, headers={HEADER: TOKEN})
    expect_error(r, 503, "internal.disabled")
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    for headers in ({}, {HEADER: "wrong"}, {HEADER: TOKEN[:-1]}, {HEADER: TOKEN + "x"}):
        r = await internal.post("/internal/collab/auth", json=body, headers=headers)
        expect_error(r, 401, "internal.unauthorized")
    r = await internal.post("/internal/collab/auth", json=body, headers={HEADER: TOKEN})
    expect_error(r, 401, "collab.session_invalid")
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
    r = await collab_auth(collab, wiki.editor, page)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"] == {"id": str(wiki.users["editor"].id), "name": "Wiki editor"}
    assert (body["generation"], body["can_edit"]) == (0, True)
    assert body["session_id"]
    expect_error(await collab_auth(collab, wiki.viewer, page), 403, "auth.permission_denied")
    expect_error(await collab_auth(collab, wiki.outsider, page), 404, "page.not_found")
    r = await collab.post(
        "/internal/collab/auth", json={"session_token": "nope", "page_id": page["id"]}
    )
    expect_error(r, 401, "collab.session_invalid")
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    expect_error(await collab_auth(collab, wiki.viewer, draft), 404, "page.not_found")
    r = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert r.status_code == 204
    expect_error(await collab_auth(collab, wiki.editor, page), 404, "page.not_found")


async def test_get_returns_content_and_ydoc_of_the_current_generation_only(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="# Start")
    sid = await session_id_of(collab, wiki.editor, page)
    url = f"/internal/collab/pages/{page['id']}"
    r = await collab.get(url, params={"session_id": sid, "generation": 0})
    assert r.status_code == 200, r.text
    assert r.json() == {"generation": 0, "ydoc_b64": None, "content_md": "# Start", "title": "Live"}
    assert (await put_live(collab, page, [sid], ydoc_b64=ydoc(b"yjs"))).status_code == 200
    r = await collab.get(url, params={"session_id": sid, "generation": 0})
    assert r.json()["ydoc_b64"] == ydoc(b"yjs") and r.json()["content_md"] == "live"
    # Saved in Markdown mode: a new generation, the old live state is not handed out.
    fresh = await get_page(wiki.editor, page)
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
    expect_error(
        await collab.get(url, params={"session_id": sid, "generation": 0}),
        409,
        "collab.generation_ended",
    )
    # A session loads only pages its person may edit.
    space = (await wiki.admin.post("/api/spaces", json={"name": "Fremd", "kind": "team"})).json()
    foreign = await new_page(wiki.admin, space["id"], "Fremd")
    r = await collab.get(f"/internal/collab/pages/{foreign['id']}", params={"session_id": sid})
    expect_error(r, 404, "page.not_found")
    published = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Offen"))
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={"member_type": "user", "member_id": str(wiki.users["editor"].id), "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    r = await collab.get(f"/internal/collab/pages/{published['id']}", params={"session_id": sid})
    expect_error(r, 403, "auth.permission_denied")
    r = await collab.get(url, params={"session_id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"})
    expect_error(r, 401, "collab.session_invalid")


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
    sid = await session_id_of(collab, wiki.editor, page)
    r = await put_live(collab, page, [sid], content_md="# Live\n\nText")
    assert r.status_code == 200, r.text
    after = await get_page(wiki.editor, page)
    assert (after["content_md"], after["collab_generation"]) == ("# Live\n\nText", 0)
    assert r.json() == {"generation": 0, "version": after["version"]}
    assert after["version"] == page["version"] + 1
    # A REST client still holding the old version gets the usual conflict.
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "x", "version": page["version"]}
    )
    expect_error(r, 409, "page.version_conflict")


async def test_put_creates_coalesced_collab_versions_per_author(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="v1")
    editor = await session_id_of(collab, wiki.editor, page)
    editor2 = await session_id_of(collab, wiki.editor2, page)
    for text in ("a", "ab", "abc"):
        assert (await put_live(collab, page, [editor], content_md=text)).status_code == 200
    versions_url = f"/api/pages/{page['id']}/versions"
    items = (await wiki.editor.get(versions_url)).json()["items"]
    assert [(v["number"], v["source"], v["author"]["name"]) for v in items] == [
        (2, "collab", "Wiki editor"),
        (1, "human", "Wiki editor"),
    ]
    assert (await wiki.editor.get(f"{versions_url}/2")).json()["content_md"] == "abc"
    # Another author gets a version of their own; a save by both folds into the
    # newest version, which is one of theirs.
    assert (await put_live(collab, page, [editor2], content_md="abcd")).status_code == 200
    assert (await put_live(collab, page, [editor2, editor], content_md="abcde")).status_code == 200
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
    assert (await put_live(collab, page, [editor2], content_md="abcdef")).status_code == 200
    # Another live session (a new document) does not fold into the old one's version.
    assert (
        await put_live(collab, page, [editor2], content_md="abcdefg", session_key="doc-2")
    ).status_code == 200
    numbers = [v["number"] for v in (await wiki.editor.get(versions_url)).json()["items"]]
    assert numbers == [5, 4, 3, 2, 1]


async def test_ydoc_over_5mb_is_413(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await session_id_of(collab, wiki.editor, page)
    big = ydoc(b"\x00" * (5 * 1024 * 1024 + 1))
    expect_error(await put_live(collab, page, [sid], ydoc_b64=big), 413, "collab.state_too_large")
    ok = ydoc(b"\x00" * (5 * 1024 * 1024))
    assert (await put_live(collab, page, [sid], ydoc_b64=ok)).status_code == 200
    # Far over the limit (still within the body limit): 413 as well, never 422.
    huge = ydoc(b"\x00" * (6 * 1024 * 1024))
    expect_error(await put_live(collab, page, [sid], ydoc_b64=huge), 413, "collab.state_too_large")


async def test_markdown_over_the_page_limit_is_413(wiki: Wiki, collab: AsyncClient) -> None:
    """Review M2 R8: the live editor says the page is too large, not "not found"."""
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await session_id_of(collab, wiki.editor, page)
    r = await put_live(collab, page, [sid], content_md="x" * 200_001)
    expect_error(r, 413, "collab.state_too_large")
    assert (await put_live(collab, page, [sid], content_md="x" * 200_000)).status_code == 200


async def test_put_refuses_bad_input(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await session_id_of(collab, wiki.editor, page)
    expect_error(
        await put_live(collab, page, [sid], ydoc_b64="!!notbase64"), 422, "collab.state_invalid"
    )
    expect_error(await put_live(collab, page, []), 422, "validation_failed")


async def test_saves_are_counted(wiki: Wiki, collab: AsyncClient) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    sid = await session_id_of(collab, wiki.editor, page)
    await put_live(collab, page, [sid])
    await put_live(collab, page, [sid], generation=7)
    text = (await collab.get("/metrics")).text
    assert 'herd_collab_saves_total{result="saved"}' in text
    assert 'herd_collab_saves_total{result="generation_ended"}' in text


async def test_unrepresentable_saves_are_counted(wiki: Wiki, collab: AsyncClient) -> None:
    # The collab process stored nothing: the document cannot be written as Markdown.
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    r = await collab.post(f"/internal/collab/pages/{page['id']}/unrepresentable")
    assert r.status_code == 204
    text = (await collab.get("/metrics")).text
    assert 'herd_collab_saves_total{result="unrepresentable"}' in text


async def test_load_mutations_are_counted(wiki: Wiki, collab: AsyncClient) -> None:
    # A browser's editor changed a document it had just loaded, before anyone typed
    # (review M2 ruling B): the browser stopped and the collab process reports it.
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    r = await collab.post(f"/internal/collab/pages/{page['id']}/load-mutation")
    assert r.status_code == 204
    text = (await collab.get("/metrics")).text
    assert "herd_collab_load_mutations_total 1.0" in text
