"""Live sessions that must end (plan M2 task 8, review focus "stale live session" and
"rights revocation"): a save of an older generation is refused, every save and check
names the editors who may no longer edit, and unsaved edits of one of them end the
generation, so no browser that saw them brings them back."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories_collab import (
    expect_error,
    get_page,
    put_live,
    session_id_of,
)
from tests.factories_wiki import Wiki, new_page, publish


async def test_put_with_old_generation_is_409_and_changes_nothing(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="alt")
    sid = await session_id_of(collab, wiki.editor, page)
    restored = await wiki.editor.post(
        f"/api/pages/{page['id']}/versions/1/restore", json={"version": page["version"]}
    )
    assert restored.json()["collab_generation"] == 1
    before = await get_page(wiki.editor, page)
    error = expect_error(
        await put_live(collab, page, [sid], generation=0), 409, "collab.generation_ended"
    )
    assert error["details"] == {"generation": 1}
    after = await get_page(wiki.editor, page)
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


async def test_put_with_revoked_editor_is_403_and_saves_nothing(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await session_id_of(collab, wiki.editor, page)
    editor2 = await session_id_of(collab, wiki.editor2, page)
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={
            "member_type": "user",
            "member_id": str(wiki.users["editor2"].id),
            "role": "viewer",
        },
    )
    assert r.status_code == 200, r.text
    error = expect_error(
        await put_live(collab, page, [editor, editor2]), 403, "collab.editors_revoked"
    )
    assert error["details"] == {
        "revoked_session_ids": [editor2],
        "revoked_user_ids": [str(wiki.users["editor2"].id)],
    }
    assert (await get_page(wiki.editor, page))["content_md"] == "a"
    r = await collab.get(
        f"/internal/collab/pages/{page['id']}", params={"session_id": editor, "generation": 0}
    )
    assert r.json()["ydoc_b64"] is None
    assert (await put_live(collab, page, [editor])).status_code == 200


async def test_ended_session_and_deactivated_user_are_revoked(
    wiki: Wiki, collab: AsyncClient
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    editor = await session_id_of(collab, wiki.editor, page)
    editor2 = await session_id_of(collab, wiki.editor2, page)
    moderator = await session_id_of(collab, wiki.moderator, page)
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
    r = await put_live(collab, page, [moderator, editor])
    assert expect_error(r, 403, "collab.editors_revoked")["details"]["revoked_session_ids"] == [
        editor
    ]
    unknown = "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"
    r = await put_live(collab, page, [unknown])
    assert expect_error(r, 403, "collab.editors_revoked")["details"]["revoked_session_ids"] == [
        unknown
    ]


async def test_unsaved_edits_of_a_revoked_editor_end_the_generation(
    wiki: Wiki, collab: AsyncClient
) -> None:
    """The live document holds edits no one may save any more: browsers that saw them
    must not bring them back by reconnecting, so the generation ends."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await session_id_of(collab, wiki.editor, page)
    editor2 = await session_id_of(collab, wiki.editor2, page)
    moderator = await session_id_of(collab, wiki.moderator, page)
    assert (await put_live(collab, page, [editor], content_md="b")).status_code == 200
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={"member_type": "user", "member_id": str(wiki.users["editor2"].id), "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    url = f"/internal/collab/pages/{page['id']}/check"
    # Revoked without unsaved edits: their connections close, the session goes on.
    body = {"session_ids": [editor, editor2], "unsaved_session_ids": [editor], "generation": 0}
    r = await collab.post(url, json=body)
    assert r.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_session_ids": [editor2],
        "revoked_user_ids": [str(wiki.users["editor2"].id)],
    }
    # With unsaved edits: the generation ends, once.
    body = {"session_ids": [editor, editor2], "unsaved_session_ids": [editor2], "generation": 0}
    r = await collab.post(url, json=body)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 1)
    assert r.json()["revoked_session_ids"] == [editor2]
    r = await collab.post(url, json=body)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 1)
    after = await get_page(wiki.editor, page)
    assert (after["content_md"], after["collab_generation"]) == ("b", 1)
    assert after["version"] == page["version"] + 1  # the generation is not a content change
    expect_error(
        await put_live(collab, page, [editor], generation=0), 409, "collab.generation_ended"
    )
    r = await collab.get(
        f"/internal/collab/pages/{page['id']}", params={"session_id": editor, "generation": 1}
    )
    assert r.json()["ydoc_b64"] is None
    # An ended session's unsaved edits end it too; any valid session names the page.
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    body = {"session_ids": [moderator], "unsaved_session_ids": [editor], "generation": 1}
    r = await collab.post(url, json=body)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 2)
    assert r.json()["revoked_session_ids"] == [editor]


async def test_check_reports_an_ended_generation(wiki: Wiki, collab: AsyncClient) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Live"))
    sid = await session_id_of(collab, wiki.editor, page)
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


async def test_unsaved_edits_end_the_generation_when_no_session_is_valid(
    wiki: Wiki, collab: AsyncClient
) -> None:
    """The internal API is trusted: the page row names the organisation, so the
    generation ends even when every session that ever joined has ended."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await session_id_of(collab, wiki.editor, page)
    editor2 = await session_id_of(collab, wiki.editor2, page)
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    assert (await wiki.editor2.post("/api/auth/logout")).status_code == 204
    url = f"/internal/collab/pages/{page['id']}/check"
    body = {"session_ids": [editor], "unsaved_session_ids": [editor2], "generation": 0}
    r = await collab.post(url, json=body)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "generation_ok": False,
        "generation": 1,
        "revoked_session_ids": sorted([editor, editor2]),
        "revoked_user_ids": [],
    }
    after = await get_page(wiki.moderator, page)
    assert (after["content_md"], after["collab_generation"]) == ("a", 1)
    # Without unsaved edits nothing ends; the ended sessions are named.
    body = {"session_ids": [editor, editor2], "generation": 1}
    r = await collab.post(url, json=body)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (True, 1)
    assert r.json()["revoked_session_ids"] == sorted([editor, editor2])
    # An unknown page is not live.
    unknown = "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"
    r = await collab.post(f"/internal/collab/pages/{unknown}/check", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["generation_ok"] is False
