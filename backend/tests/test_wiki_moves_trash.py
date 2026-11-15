"""Moving and ordering pages, the trash and purging (plan M2 task 2)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.modules.audit.models import AuditLog
from app.modules.wiki.models import Page
from tests.factories_wiki import Wiki, new_page, publish


async def _move(
    client: AsyncClient, page: dict[str, Any], parent: dict[str, Any] | None, **extra: Any
) -> Any:
    body = {"parent_id": parent["id"] if parent else None, "version": page["version"], **extra}
    return await client.post(f"/api/pages/{page['id']}/move", json=body)


async def _get(client: AsyncClient, page: dict[str, Any]) -> dict[str, Any]:
    r = await client.get(f"/api/pages/{page['id']}")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


async def _trash(client: AsyncClient, page: dict[str, Any]) -> Any:
    return await client.post(f"/api/pages/{page['id']}/trash", json={"version": page["version"]})


async def _tree_paths(client: AsyncClient, wiki: Wiki) -> list[str]:
    r = await client.get(f"/api/spaces/{wiki.space_id}/pages/tree", params={"limit": 100})
    return [n["path"] for n in r.json()["items"]]


async def _trash_ids(client: AsyncClient, wiki: Wiki) -> list[str]:
    r = await client.get(f"/api/spaces/{wiki.space_id}/trash")
    assert r.status_code == 200, r.text
    return [p["id"] for p in r.json()["items"]]


# --- moving ------------------------------------------------------------------------


async def test_move_rewrites_descendant_paths(wiki: Wiki) -> None:
    it = await new_page(wiki.editor, wiki.space_id, "IT")
    hr = await new_page(wiki.editor, wiki.space_id, "HR")
    access = await new_page(wiki.editor, wiki.space_id, "Zugänge", parent_id=it["id"])
    await new_page(wiki.editor, wiki.space_id, "VPN", parent_id=access["id"])
    r = await _move(wiki.editor, access, hr)
    assert r.status_code == 200, r.text
    moved = r.json()
    assert (moved["parent_id"], moved["path"], moved["version"]) == (hr["id"], "hr/zugaenge", 2)
    assert await _tree_paths(wiki.editor, wiki) == ["hr", "hr/zugaenge", "hr/zugaenge/vpn", "it"]
    r = await _move(wiki.editor, moved, None)
    assert r.json()["path"] == "zugaenge" and r.json()["parent_id"] is None
    assert "zugaenge/vpn" in await _tree_paths(wiki.editor, wiki)


async def test_move_next_to_a_namesake_gets_a_suffix(wiki: Wiki) -> None:
    a = await new_page(wiki.editor, wiki.space_id, "A")
    await new_page(wiki.editor, wiki.space_id, "Notizen", parent_id=a["id"])
    notes = await new_page(wiki.editor, wiki.space_id, "Notizen")
    r = await _move(wiki.editor, notes, a)
    assert (r.json()["slug"], r.json()["path"]) == ("notizen-2", "a/notizen-2")


async def test_move_orders_siblings(wiki: Wiki) -> None:
    pages = [await new_page(wiki.editor, wiki.space_id, t) for t in ("Eins", "Zwei", "Drei")]
    r = await _move(wiki.editor, pages[2], None, position=0)
    assert r.status_code == 200, r.text
    order = {p["id"]: (await _get(wiki.editor, p))["sort_order"] for p in pages}
    assert [order[p["id"]] for p in pages] == [1, 2, 0]
    # Moving under a new parent without a position appends.
    parent = pages[0]
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=parent["id"])
    r = await _move(wiki.editor, await _get(wiki.editor, pages[1]), parent)
    assert r.json()["sort_order"] == child["sort_order"] + 1
    # A position past the end is the end.
    r = await _move(wiki.editor, child, parent, position=99)
    assert r.json()["sort_order"] == 1


async def test_move_into_own_subtree_is_409(wiki: Wiki) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Wurzel")
    child = await new_page(wiki.editor, wiki.space_id, "Ast", parent_id=root["id"])
    leaf = await new_page(wiki.editor, wiki.space_id, "Blatt", parent_id=child["id"])
    for target in (root, child, leaf):
        r = await _move(wiki.editor, root, target)
        assert r.status_code == 409 and r.json()["error"]["code"] == "page.move_cycle"
    assert await _tree_paths(wiki.editor, wiki) == ["wurzel", "wurzel/ast", "wurzel/ast/blatt"]


async def test_move_to_other_space_is_422(wiki: Wiki, make_space) -> None:
    other = await make_space("open", "Anderswo")
    foreign = await new_page(wiki.admin, other.id, "Fremd")
    page = await new_page(wiki.editor, wiki.space_id, "Hier")
    r = await _move(wiki.editor, page, foreign)
    assert r.status_code == 422 and r.json()["error"]["code"] == "page.move_other_space"
    r = await wiki.editor.post(
        f"/api/pages/{page['id']}/move", json={"parent_id": str(uuid7()), "version": 1}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "page.parent_not_found"


async def test_move_that_would_exceed_16_levels_is_422(wiki: Wiki) -> None:
    parent_id = None
    for depth in range(15):
        parent_id = (await new_page(wiki.editor, wiki.space_id, f"T{depth}", parent_id=parent_id))[
            "id"
        ]
    branch = await new_page(wiki.editor, wiki.space_id, "Ast")
    await new_page(wiki.editor, wiki.space_id, "Zweig", parent_id=branch["id"])
    r = await _move(wiki.editor, branch, {"id": parent_id})
    assert r.status_code == 422 and r.json()["error"]["code"] == "page.too_deep"


async def test_move_needs_edit_right_and_current_version(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    r = await _move(wiki.viewer, page, None)
    assert r.status_code == 403
    r = await _move(wiki.editor, {**page, "version": 1}, None)
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.version_conflict"


# --- trash -------------------------------------------------------------------------


async def test_trash_hides_page_and_descendants_from_tree_get_and_path(wiki: Wiki) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Alt")
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=root["id"])
    keep = await new_page(wiki.editor, wiki.space_id, "Bleibt")
    r = await _trash(wiki.moderator, root)
    assert r.status_code == 204, r.text
    for page in (root, child):
        r = await wiki.editor.get(f"/api/pages/{page['id']}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"
    r = await wiki.editor.get(
        f"/api/spaces/{wiki.space_id}/pages/by-path", params={"path": "alt/kind"}
    )
    assert r.status_code == 404
    assert await _tree_paths(wiki.editor, wiki) == [keep["path"]]
    assert await _trash_ids(wiki.moderator, wiki) == [root["id"]]  # the batch's root
    # The path is free again.
    assert (await new_page(wiki.editor, wiki.space_id, "Alt"))["path"] == "alt"


async def test_restore_brings_back_descendants_trashed_together_only(wiki: Wiki) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Projekt")
    early = await new_page(wiki.editor, wiki.space_id, "Früh", parent_id=root["id"])
    late = await new_page(wiki.editor, wiki.space_id, "Spät", parent_id=root["id"])
    assert (await _trash(wiki.moderator, early)).status_code == 204
    root = await _get(wiki.editor, root)
    assert (await _trash(wiki.moderator, root)).status_code == 204
    assert set(await _trash_ids(wiki.moderator, wiki)) == {root["id"], early["id"]}
    r = await wiki.moderator.post(f"/api/pages/{root['id']}/restore")
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "projekt"
    assert await _tree_paths(wiki.editor, wiki) == ["projekt", "projekt/spaet"]
    assert (await _get(wiki.editor, late))["parent_id"] == root["id"]
    assert await _trash_ids(wiki.moderator, wiki) == [early["id"]]
    # Its parent is back: the earlier page returns to where it was.
    r = await wiki.moderator.post(f"/api/pages/{early['id']}/restore")
    assert (r.json()["path"], r.json()["parent_id"]) == ("projekt/frueh", root["id"])


async def test_restore_with_trashed_parent_lands_on_top_level(wiki: Wiki) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Oben")
    child = await new_page(wiki.editor, wiki.space_id, "Unten", parent_id=root["id"])
    grandchild = await new_page(wiki.editor, wiki.space_id, "Ganz", parent_id=child["id"])
    assert (await _trash(wiki.moderator, root)).status_code == 204
    r = await wiki.moderator.post(f"/api/pages/{child['id']}/restore")
    assert r.status_code == 200, r.text
    assert (r.json()["path"], r.json()["parent_id"]) == ("unten", None)
    assert (await _get(wiki.editor, grandchild))["path"] == "unten/ganz"
    assert await _trash_ids(wiki.moderator, wiki) == [root["id"]]


async def test_restore_with_taken_path_is_409(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Doppelt")
    assert (await _trash(wiki.moderator, page)).status_code == 204
    await new_page(wiki.editor, wiki.space_id, "Doppelt")
    r = await wiki.moderator.post(f"/api/pages/{page['id']}/restore")
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.path_taken"
    assert await _trash_ids(wiki.moderator, wiki) == [page["id"]]


async def test_editor_cannot_trash_moderator_can(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    for client in (wiki.editor, wiki.viewer):
        r = await _trash(client, page)
        assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"
        assert (await client.get(f"/api/spaces/{wiki.space_id}/trash")).status_code == 403
    r = await _trash(wiki.moderator, {**page, "version": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.version_conflict"
    assert (await _trash(wiki.moderator, page)).status_code == 204
    r = await wiki.editor.post(f"/api/pages/{page['id']}/restore")
    assert r.status_code == 403
    r = await wiki.viewer.post(f"/api/pages/{page['id']}/restore")
    assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"
    r = await wiki.outsider.get(f"/api/spaces/{wiki.space_id}/trash")
    assert r.status_code == 404 and r.json()["error"]["code"] == "space.not_found"


async def test_trash_list_is_paginated_newest_first(wiki: Wiki) -> None:
    pages = [await new_page(wiki.editor, wiki.space_id, f"P{i}") for i in range(3)]
    for page in pages:
        assert (await _trash(wiki.moderator, page)).status_code == 204
    trash = f"/api/spaces/{wiki.space_id}/trash"
    first = (await wiki.moderator.get(trash, params={"limit": 2})).json()
    rest = (
        await wiki.moderator.get(trash, params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    ids = [p["id"] for p in first["items"] + rest["items"]]
    assert ids == [p["id"] for p in reversed(pages)] and rest["next_cursor"] is None
    item = rest["items"][0]
    assert (item["title"], item["path"], item["parent_id"], item["status"]) == (
        "P0",
        "p0",
        None,
        "draft",
    )
    assert item["trashed_at"]


async def test_only_system_admin_can_purge(wiki: Wiki, session: AsyncSession) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Weg")
    child = await new_page(wiki.editor, wiki.space_id, "Auch", parent_id=root["id"])
    r = await wiki.admin.delete(f"/api/pages/{root['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.not_trashed"
    assert (await _trash(wiki.moderator, root)).status_code == 204
    for client in (wiki.editor, wiki.moderator, wiki.outsider):
        r = await client.delete(f"/api/pages/{root['id']}")
        assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"
    assert (await wiki.admin.delete(f"/api/pages/{root['id']}")).status_code == 204
    assert await _trash_ids(wiki.moderator, wiki) == []
    count = select(func.count()).select_from(Page).where(Page.id.in_([root["id"], child["id"]]))
    assert await session.scalar(count) == 0
    r = await wiki.admin.delete(f"/api/pages/{root['id']}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"


async def test_move_and_trash_bump_collab_generation(wiki: Wiki) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Live")
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=root["id"])
    moved = (await _move(wiki.editor, root, None, position=0)).json()
    assert moved["collab_generation"] == 1
    assert (await _get(wiki.editor, child))["collab_generation"] == 0
    assert (await _trash(wiki.moderator, moved)).status_code == 204
    restored = (await wiki.moderator.post(f"/api/pages/{root['id']}/restore")).json()
    assert restored["collab_generation"] == 3  # trash and restore each end the sessions
    assert (await _get(wiki.editor, child))["collab_generation"] == 2


async def test_moves_and_trash_are_audited(wiki: Wiki, session: AsyncSession) -> None:
    a = await new_page(wiki.editor, wiki.space_id, "A")
    b = await new_page(wiki.editor, wiki.space_id, "B")
    moved = (await _move(wiki.editor, b, a)).json()
    assert (await _trash(wiki.moderator, moved)).status_code == 204
    assert (await wiki.moderator.post(f"/api/pages/{b['id']}/restore")).status_code == 200
    restored = await _get(wiki.editor, b)
    assert (await _trash(wiki.moderator, restored)).status_code == 204
    assert (await wiki.admin.delete(f"/api/pages/{b['id']}")).status_code == 204
    rows = (
        await session.scalars(
            select(AuditLog).where(AuditLog.target_id == b["id"]).order_by(AuditLog.created_at)
        )
    ).all()
    assert [r.action for r in rows] == [
        "page.created",
        "page.moved",
        "page.trashed",
        "page.restored",
        "page.trashed",
        "page.purged",
    ]
    assert rows[1].details == {"from": "b", "to": "a/b"}
    assert rows[2].details == {"pages": 1}
    assert rows[5].details == {"title": "B", "path": "a/b", "pages": 1}
