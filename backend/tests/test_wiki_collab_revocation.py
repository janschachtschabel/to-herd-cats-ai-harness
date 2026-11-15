"""Live sessions that must end (plan M2 task 8, review focus "stale live session" and
"rights revocation"): a save of an older generation is refused, every save and check
names the grants whose people may no longer edit, and unsaved edits through one of
them end the generation, so no browser that saw them brings them back."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories_collab import check, expect_error, get_page, grant_of, load, put_live
from tests.factories_wiki import Wiki, new_page, publish


async def test_put_with_old_generation_is_409_and_changes_nothing(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="alt")
    sid = await grant_of(session, wiki.editor, page)
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
    r = await load(collab, await grant_of(session, wiki.editor, page, 1), page, 1)
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
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await grant_of(session, wiki.editor, page)
    editor2 = await grant_of(session, wiki.editor2, page)
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
    assert "details" not in error  # no grant goes into an error
    assert (await get_page(wiki.editor, page))["content_md"] == "a"
    r = await load(collab, editor, page)
    assert r.json()["ydoc_b64"] is None
    assert (await put_live(collab, page, [editor])).status_code == 200


async def test_deactivated_user_is_revoked_and_a_logout_has_ended(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    editor = await grant_of(session, wiki.editor, page)
    editor2 = await grant_of(session, wiki.editor2, page)
    moderator = await grant_of(session, wiki.moderator, page)
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    r = await wiki.admin.post(f"/api/admin/users/{wiki.users['editor2'].id}/deactivate")
    assert r.status_code == 204, r.text
    r = await check(collab, page, [editor, editor2, moderator])
    assert r.status_code == 200, r.text
    assert r.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_grants": [editor2],  # the deactivation deleted the sessions
        "ended_grants": [editor],  # a logout is no revocation (review M2 R2)
    }
    expect_error(await put_live(collab, page, [moderator, editor2]), 403, "collab.editors_revoked")
    assert (await put_live(collab, page, [moderator, editor])).status_code == 200
    unknown = "herd_cg_" + "x" * 43
    expect_error(await put_live(collab, page, [unknown]), 403, "collab.editors_revoked")
    expect_error(await put_live(collab, page, [moderator, unknown]), 403, "collab.editors_revoked")


async def test_unsaved_edits_of_a_revoked_editor_end_the_generation(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    """The live document holds edits no one may save any more: browsers that saw them
    must not bring them back by reconnecting, so the generation ends."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await grant_of(session, wiki.editor, page)
    editor2 = await grant_of(session, wiki.editor2, page)
    moderator = await grant_of(session, wiki.moderator, page)
    assert (await put_live(collab, page, [editor], content_md="b")).status_code == 200
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={"member_type": "user", "member_id": str(wiki.users["editor2"].id), "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    # Revoked without unsaved edits: their connections close, the session goes on.
    r = await check(collab, page, [editor, editor2], unsaved=[editor])
    assert r.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_grants": [editor2],
        "ended_grants": [],
    }
    # With unsaved edits: the generation ends, once.
    r = await check(collab, page, [editor, editor2], unsaved=[editor2])
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 1)
    assert r.json()["revoked_grants"] == [editor2]
    r = await check(collab, page, [editor, editor2], unsaved=[editor2])
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 1)
    after = await get_page(wiki.editor, page)
    assert (after["content_md"], after["collab_generation"]) == ("b", 1)
    assert after["version"] == page["version"] + 1  # the generation is not a content change
    expect_error(
        await put_live(collab, page, [editor], generation=0), 409, "collab.generation_ended"
    )
    editor = await grant_of(session, wiki.editor, page, 1)
    moderator = await grant_of(session, wiki.moderator, page, 1)
    r = await load(collab, editor, page, 1)
    assert r.json()["ydoc_b64"] is None
    # A deactivated person's unsaved edits end it too.
    r = await wiki.admin.post(f"/api/admin/users/{wiki.users['editor'].id}/deactivate")
    assert r.status_code == 204, r.text
    r = await check(collab, page, [moderator], unsaved=[editor], generation=1)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 2)
    assert r.json()["revoked_grants"] == [editor]


async def test_check_reports_an_ended_generation(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Live"))
    sid = await grant_of(session, wiki.editor, page)
    r = await check(collab, page, [sid])
    assert r.json()["generation_ok"] is True
    moved = await wiki.editor.post(
        f"/api/pages/{page['id']}/move", json={"parent_id": None, "version": page["version"]}
    )
    assert moved.status_code == 200, moved.text
    r = await check(collab, page, [sid])
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 1)
    await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": moved.json()["version"]}
    )
    r = await check(collab, page, [sid], generation=2)
    assert r.json()["generation_ok"] is False  # in the trash: no live session


async def test_unsaved_edits_end_the_generation_when_no_session_is_valid(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    """The page row names the organisation, so the generation ends even when every
    grant that ever joined is powerless (its people deactivated)."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    editor = await grant_of(session, wiki.editor, page)
    editor2 = await grant_of(session, wiki.editor2, page)
    for name in ("editor", "editor2"):
        r = await wiki.admin.post(f"/api/admin/users/{wiki.users[name].id}/deactivate")
        assert r.status_code == 204, r.text
    r = await check(collab, page, [editor], unsaved=[editor2])
    assert r.status_code == 200, r.text
    assert r.json() == {
        "generation_ok": False,
        "generation": 1,
        "revoked_grants": sorted([editor, editor2]),
        "ended_grants": [],
    }
    after = await get_page(wiki.moderator, page)
    assert (after["content_md"], after["collab_generation"]) == ("a", 1)
    # Without unsaved edits nothing ends; the revoked grants are named.
    r = await check(collab, page, [editor, editor2], generation=1)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (True, 1)
    assert r.json()["revoked_grants"] == sorted([editor, editor2])
    # An unknown page is not live.
    unknown = {"id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d"}
    r = await check(collab, unknown, [editor, editor2], generation=1)
    assert r.status_code == 200, r.text
    assert r.json()["generation_ok"] is False
