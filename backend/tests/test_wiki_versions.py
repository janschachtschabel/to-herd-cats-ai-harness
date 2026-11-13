"""Page versions: one per save, coalescing within a live session, diff, labels and
restoring an old state as a new version (plan M2 task 3)."""

from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import actor_for
from app.core.config import Settings, get_settings
from app.modules.audit.models import AuditLog
from app.modules.auth.context import AuthContext
from app.modules.users.models import User
from app.modules.wiki.models import Page, PageVersion, VersionSource
from app.modules.wiki.service import PageService
from app.modules.wiki.versions import VersionService
from tests.factories_wiki import Wiki, new_page, publish


async def _patch(client: AsyncClient, page: dict[str, Any], **body: Any) -> dict[str, Any]:
    r = await client.patch(f"/api/pages/{page['id']}", json={"version": page["version"], **body})
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


async def _versions(client: AsyncClient, page: dict[str, Any], **params: Any) -> Any:
    r = await client.get(f"/api/pages/{page['id']}/versions", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_every_save_creates_a_version_with_author(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="eins")
    page = await _patch(wiki.editor2, page, content_md="zwei", change_summary="Tippfehler")
    page = await _patch(wiki.editor2, page, title="Regeln")  # nothing changes: no version
    page = await publish(wiki.editor, page)  # not a content change: no version
    items = (await _versions(wiki.editor, page))["items"]
    editor, editor2 = wiki.users["editor"], wiki.users["editor2"]
    assert [
        (v["number"], v["author"], v["source"], v["change_summary"], v["title"], v["label"])
        for v in items
    ] == [
        (
            2,
            {"type": "user", "id": str(editor2.id), "name": editor2.name},
            "human",
            "Tippfehler",
            "Regeln",
            None,
        ),
        (
            1,
            {"type": "user", "id": str(editor.id), "name": editor.name},
            "human",
            None,
            "Regeln",
            None,
        ),
    ]
    assert all(v["created_at"] for v in items) and "content_md" not in items[0]
    one = await wiki.editor.get(f"/api/pages/{page['id']}/versions/1")
    assert one.status_code == 200 and one.json()["content_md"] == "eins"
    missing = await wiki.editor.get(f"/api/pages/{page['id']}/versions/9")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "page.version_not_found"


async def test_versions_are_paginated_newest_first(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Viele")
    for text in ("a", "b", "c"):
        page = await _patch(wiki.editor, page, content_md=text)
    first = await _versions(wiki.editor, page, limit=3)
    rest = await _versions(wiki.editor, page, limit=3, cursor=first["next_cursor"])
    assert [v["number"] for v in first["items"]] == [4, 3, 2]
    assert [v["number"] for v in rest["items"]] == [1] and rest["next_cursor"] is None


async def test_restore_creates_new_version_and_keeps_history(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Alt", content_md="alt")
    page = await _patch(wiki.editor, page, title="Neu", content_md="neu")
    r = await wiki.editor2.post(
        f"/api/pages/{page['id']}/versions/1/restore", json={"version": page["version"]}
    )
    assert r.status_code == 200, r.text
    restored = r.json()
    assert (restored["content_md"], restored["title"], restored["path"]) == ("alt", "Neu", "alt")
    assert (restored["version"], restored["collab_generation"]) == (
        page["version"] + 1,
        page["collab_generation"] + 1,  # the PATCH ended one generation, the restore the next
    )
    assert page["collab_generation"] == 1
    items = (await _versions(wiki.editor, page))["items"]
    assert [(v["number"], v["source"], v["change_summary"]) for v in items] == [
        (3, "restore", "restore:1"),
        (2, "human", None),
        (1, "human", None),
    ]
    assert items[0]["author"]["id"] == str(wiki.users["editor2"].id)
    audit = await session.scalar(
        select(AuditLog).where(
            AuditLog.target_id == page["id"], AuditLog.action == "page.version_restored"
        )
    )
    assert audit is not None and audit.details == {"number": 1}


async def test_restore_with_stale_page_version_is_409(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Seite", content_md="a")
    await _patch(wiki.editor, page, content_md="b")
    r = await wiki.editor.post(f"/api/pages/{page['id']}/versions/1/restore", json={"version": 1})
    assert r.status_code == 409 and r.json()["error"]["details"] == {"current_version": 2}


async def test_diff_marks_inserted_and_deleted_lines(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Liste", content_md="a\nb\nc\nd")
    page = await _patch(wiki.editor, page, title="Liste neu", content_md="a\nB\nc\nd\ne")
    r = await wiki.editor.get(f"/api/pages/{page['id']}/diff", params={"from": 1, "to": 2})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "from_number": 1,
        "to_number": 2,
        "title_changed": True,
        "from_title": "Liste",
        "to_title": "Liste neu",
        "hunks": [
            {"kind": "equal", "lines": ["a"]},
            {"kind": "delete", "lines": ["b"]},
            {"kind": "insert", "lines": ["B"]},
            {"kind": "equal", "lines": ["c", "d"]},
            {"kind": "insert", "lines": ["e"]},
        ],
    }
    same = await wiki.editor.get(f"/api/pages/{page['id']}/diff", params={"from": 2, "to": 2})
    assert same.json()["title_changed"] is False
    assert same.json()["hunks"] == [{"kind": "equal", "lines": ["a", "B", "c", "d", "e"]}]
    r = await wiki.editor.get(f"/api/pages/{page['id']}/diff", params={"from": 1, "to": 7})
    assert r.status_code == 404 and r.json()["error"]["code"] == "page.version_not_found"


async def test_labels_name_a_version(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    path = f"/api/pages/{page['id']}/versions/1"
    r = await wiki.editor.patch(path, json={"label": "Freigabe 2026"})
    assert r.status_code == 200 and r.json()["label"] == "Freigabe 2026"
    assert (await _versions(wiki.editor, page))["items"][0]["label"] == "Freigabe 2026"
    assert (await wiki.editor.patch(path, json={"label": None})).json()["label"] is None
    assert (await wiki.editor.patch(path, json={"label": "x" * 101})).status_code == 422


async def test_version_history_needs_page_edit(wiki: Wiki) -> None:
    """Review M2 R16: viewers see the current published content only, not the history
    (draft-time versions and their authors included), its diffs or restores."""
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    for path in (
        f"/api/pages/{draft['id']}/versions",
        f"/api/pages/{draft['id']}/versions/1",
        f"/api/pages/{draft['id']}/diff?from=1&to=1",
    ):
        r = await wiki.viewer.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found", path
    page = await publish(wiki.editor, draft)
    assert (await wiki.viewer.get(f"/api/pages/{page['id']}")).status_code == 200
    for r in (
        await wiki.viewer.get(f"/api/pages/{page['id']}/versions"),
        await wiki.viewer.get(f"/api/pages/{page['id']}/versions/1"),
        await wiki.viewer.get(f"/api/pages/{page['id']}/diff?from=1&to=1"),
        await wiki.viewer.patch(f"/api/pages/{page['id']}/versions/1", json={"label": "x"}),
        await wiki.viewer.post(
            f"/api/pages/{page['id']}/versions/1/restore", json={"version": page["version"]}
        ),
    ):
        assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"
    assert [v["number"] for v in (await _versions(wiki.editor, page))["items"]] == [1]


async def test_purge_removes_versions(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Weg", content_md="a")
    page = await _patch(wiki.editor, page, content_md="b")
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert trashed.status_code == 204
    assert (await wiki.admin.delete(f"/api/pages/{page['id']}")).status_code == 204
    count = select(func.count()).select_from(PageVersion).where(PageVersion.page_id == page["id"])
    assert await session.scalar(count) == 0


# --- coalescing (service level; the live session of task 8 is its caller) ---------


async def _record(
    session: AsyncSession, page_id: object, user: User, content: str, key: str | None
) -> PageVersion:
    actor = await actor_for(session, AuthContext(user=user))
    page = await session.get(Page, page_id)
    assert page is not None
    page.content_md = content
    return await VersionService(session).record(
        page, actor, VersionSource.COLLAB, session_key=key, coalesce_seconds=60
    )


async def test_coalesce_overwrites_within_window_same_author_and_session(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    editor = wiki.users["editor"]
    first = await _record(session, page["id"], editor, "eins", "s1")
    second = await _record(session, page["id"], editor, "zwei", "s1")
    assert (second.id, second.number, second.content_md) == (first.id, 2, "zwei")
    await session.execute(
        update(PageVersion)
        .where(PageVersion.id == first.id)
        .values(created_at=first.created_at - timedelta(seconds=61))
    )
    third = await _record(session, page["id"], editor, "drei", "s1")
    assert third.number == 3
    numbers = (await _versions(wiki.editor, page))["items"]
    assert [(v["number"], v["source"]) for v in numbers] == [
        (3, "collab"),
        (2, "collab"),
        (1, "human"),
    ]


async def test_coalesce_does_not_merge_different_authors_or_sessions(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    editor, editor2 = wiki.users["editor"], wiki.users["editor2"]
    numbers = [
        (await _record(session, page["id"], editor, "a", "s1")).number,
        (await _record(session, page["id"], editor2, "b", "s1")).number,
        (await _record(session, page["id"], editor2, "c", "s2")).number,
        (await _record(session, page["id"], editor2, "d", None)).number,
        (await _record(session, page["id"], editor2, "e", None)).number,
    ]
    assert numbers == [2, 3, 4, 5, 6]
    # A human save after a live one is never folded into it.
    service = PageService(session)
    actor = await actor_for(session, AuthContext(user=editor2))
    current = await session.get(Page, page["id"])
    assert current is not None
    await service.update(actor, current.id, content_md="f", version=current.version)
    assert (await _versions(wiki.editor, page))["items"][0]["number"] == 7


def test_the_diff_limit_defaults_to_20000_lines() -> None:
    assert Settings().diff_max_lines == 20_000


async def test_diff_over_the_line_limit_is_422(wiki: Wiki, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "diff_max_lines", 6)
    page = await new_page(wiki.editor, wiki.space_id, "Lang", content_md="a\nb\nc")
    page = await _patch(wiki.editor, page, content_md="a\nb\nc\nd")
    diff = f"/api/pages/{page['id']}/diff"
    assert (await wiki.editor.get(diff, params={"from": 1, "to": 1})).status_code == 200
    r = await wiki.editor.get(diff, params={"from": 1, "to": 2})
    assert r.status_code == 422 and r.json()["error"]["code"] == "page.diff_too_large"
