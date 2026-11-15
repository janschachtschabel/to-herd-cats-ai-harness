"""Wiki pages: creation, the tree, editing with optimistic locking, publishing, and
who sees and may do what (spec 9, plan M2 task 1)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import AuditLog
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.wiki.service import PageService
from tests.factories_wiki import Wiki, new_page, publish


async def test_create_page_sets_slug_path_version_and_author(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Onboarding Prozess", content_md="# Hallo")
    editor = wiki.users["editor"]
    assert (page["slug"], page["path"], page["parent_id"]) == (
        "onboarding-prozess",
        "onboarding-prozess",
        None,
    )
    assert (page["version"], page["status"], page["content_md"]) == (1, "draft", "# Hallo")
    assert (page["collab_generation"], page["published_at"], page["space_id"]) == (
        0,
        None,
        wiki.space_id,
    )
    assert page["created_by"] == page["updated_by"] == {"type": "user", "id": str(editor.id)}
    assert (await wiki.editor.get(f"/api/pages/{page['id']}")).json() == page


async def test_slug_collision_gets_numeric_suffix(wiki: Wiki) -> None:
    parent = await new_page(wiki.editor, wiki.space_id, "IT")
    first = await new_page(wiki.editor, wiki.space_id, "Zugänge", parent_id=parent["id"])
    twin = await new_page(wiki.editor, wiki.space_id, "Zugänge", parent_id=parent["id"])
    third = await new_page(wiki.editor, wiki.space_id, "zugänge!", parent_id=parent["id"])
    assert [p["path"] for p in (first, twin, third)] == [
        "it/zugaenge",
        "it/zugaenge-2",
        "it/zugaenge-3",
    ]
    assert [p["sort_order"] for p in (first, twin, third)] == [0, 1, 2]
    # The same title elsewhere in the tree is no collision.
    assert (await new_page(wiki.editor, wiki.space_id, "Zugänge"))["path"] == "zugaenge"


async def test_title_without_letters_still_gets_a_slug(wiki: Wiki) -> None:
    assert (await new_page(wiki.editor, wiki.space_id, "???"))["slug"] == "seite"


async def test_tree_is_flat_sorted_by_path_and_paginated(wiki: Wiki) -> None:
    b = await new_page(wiki.editor, wiki.space_id, "B")
    a = await new_page(wiki.editor, wiki.space_id, "A")
    b1 = await new_page(wiki.editor, wiki.space_id, "B1", parent_id=b["id"])
    tree = f"/api/spaces/{wiki.space_id}/pages/tree"
    first = (await wiki.editor.get(tree, params={"limit": 2})).json()
    assert [n["path"] for n in first["items"]] == ["a", "b"]
    assert first["next_cursor"]
    rest = (await wiki.editor.get(tree, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    assert rest["next_cursor"] is None
    assert rest["items"] == [
        {
            "id": b1["id"],
            "parent_id": b["id"],
            "title": "B1",
            "slug": "b1",
            "path": "b/b1",
            "status": "draft",
            "sort_order": 0,
            "tags": [],
            "review_due": False,
        }
    ]
    assert first["items"][0]["id"] == a["id"]
    assert [n["sort_order"] for n in first["items"]] == [1, 0]  # creation order


async def test_get_by_path(wiki: Wiki) -> None:
    parent = await new_page(wiki.editor, wiki.space_id, "Handbuch")
    child = await new_page(wiki.editor, wiki.space_id, "Urlaub", parent_id=parent["id"])
    by_path = f"/api/spaces/{wiki.space_id}/pages/by-path"
    r = await wiki.editor.get(by_path, params={"path": "handbuch/urlaub"})
    assert r.status_code == 200 and r.json()["id"] == child["id"]
    missing = await wiki.editor.get(by_path, params={"path": "handbuch/nichts"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "page.not_found"


async def test_update_bumps_version_and_keeps_slug(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln")
    r = await wiki.editor2.patch(
        f"/api/pages/{page['id']}", json={"title": "Neue Regeln", "content_md": "v2", "version": 1}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["version"], body["title"], body["content_md"]) == (2, "Neue Regeln", "v2")
    assert (body["slug"], body["path"]) == ("regeln", "regeln")  # addresses stay stable
    assert body["updated_by"]["id"] == str(wiki.users["editor2"].id)
    assert body["created_by"]["id"] == str(wiki.users["editor"].id)


async def test_stale_version_is_409_and_returns_current_version(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln")
    path = f"/api/pages/{page['id']}"
    assert (await wiki.editor.patch(path, json={"content_md": "v2", "version": 1})).is_success
    r = await wiki.editor2.patch(path, json={"content_md": "v3", "version": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.version_conflict"
    assert r.json()["error"]["details"] == {"current_version": 2}
    assert (await wiki.editor.get(path)).json()["content_md"] == "v2"


async def test_content_over_200000_chars_is_422(wiki: Wiki) -> None:
    create = f"/api/spaces/{wiki.space_id}/pages"
    r = await wiki.editor.post(create, json={"title": "Lang", "content_md": "x" * 200_001})
    assert r.status_code == 422
    page = await new_page(wiki.editor, wiki.space_id, "Lang", content_md="x" * 200_000)
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "ä" * 200_001, "version": 1}
    )
    assert r.status_code == 422


async def test_more_than_16_path_segments_is_422(wiki: Wiki) -> None:
    parent_id = None
    for depth in range(16):
        parent_id = (await new_page(wiki.editor, wiki.space_id, f"E{depth}", parent_id=parent_id))[
            "id"
        ]
    r = await wiki.editor.post(
        f"/api/spaces/{wiki.space_id}/pages", json={"title": "Zu tief", "parent_id": parent_id}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "page.too_deep"


async def test_parent_must_be_a_page_of_the_same_space(wiki: Wiki, make_space) -> None:
    other = await make_space("open", "Anderswo")
    foreign = await new_page(wiki.admin, other.id, "Fremd")
    for parent_id in (foreign["id"], str(uuid7())):
        r = await wiki.editor.post(
            f"/api/spaces/{wiki.space_id}/pages", json={"title": "Kind", "parent_id": parent_id}
        )
        assert r.status_code == 422 and r.json()["error"]["code"] == "page.parent_not_found"


async def test_viewer_does_not_see_drafts_in_tree_or_by_id(wiki: Wiki) -> None:
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    done = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Fertig"))
    tree = f"/api/spaces/{wiki.space_id}/pages/tree"
    assert [n["id"] for n in (await wiki.viewer.get(tree)).json()["items"]] == [done["id"]]
    for r in (
        await wiki.viewer.get(f"/api/pages/{draft['id']}"),
        await wiki.viewer.get(
            f"/api/spaces/{wiki.space_id}/pages/by-path", params={"path": "entwurf"}
        ),
        await wiki.viewer.patch(f"/api/pages/{draft['id']}", json={"title": "x", "version": 1}),
    ):
        assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"
    assert (await wiki.viewer.get(f"/api/pages/{done['id']}")).status_code == 200
    # Everyone with page.edit sees drafts, not only their author.
    assert {n["id"] for n in (await wiki.editor2.get(tree)).json()["items"]} == {
        draft["id"],
        done["id"],
    }
    assert (await wiki.admin.get(f"/api/pages/{draft['id']}")).status_code == 200


async def test_viewer_may_read_but_not_write(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    r = await wiki.viewer.patch(f"/api/pages/{page['id']}", json={"title": "x", "version": 2})
    assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"
    r = await wiki.viewer.post(f"/api/spaces/{wiki.space_id}/pages", json={"title": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"


async def test_page_in_invisible_space_is_404_like_unknown_id(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Geheim"))
    outsider = wiki.outsider
    for page_id in (page["id"], str(uuid7())):
        for r in (
            await outsider.get(f"/api/pages/{page_id}"),
            await outsider.patch(f"/api/pages/{page_id}", json={"title": "x", "version": 2}),
            await outsider.post(f"/api/pages/{page_id}/publish", json={"version": 2}),
        ):
            assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"
    for space_id in (wiki.space_id, str(uuid7())):
        for r in (
            await outsider.get(f"/api/spaces/{space_id}/pages/tree"),
            await outsider.get(f"/api/spaces/{space_id}/pages/by-path", params={"path": "geheim"}),
            await outsider.post(f"/api/spaces/{space_id}/pages", json={"title": "x"}),
        ):
            assert r.status_code == 404 and r.json()["error"]["code"] == "space.not_found"


async def test_pages_of_another_organisation_are_invisible(
    wiki: Wiki, session: AsyncSession, make_user
) -> None:
    elsewhere = Organization(name="Elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user("owner", organization=elsewhere)
    space = Space(org_id=elsewhere.id, kind=SpaceKind.OPEN, name="Fremd")
    session.add(space)
    await session.flush()
    actor = Actor(elsewhere.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    page = await PageService(session).create(actor, space.id, None, "Intern")
    r = await wiki.admin.get(f"/api/pages/{page.id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"
    r = await wiki.admin.get(f"/api/spaces/{space.id}/pages/tree")
    assert r.status_code == 404 and r.json()["error"]["code"] == "space.not_found"


async def test_editor_publishes_own_draft_but_not_someone_elses(wiki: Wiki) -> None:
    own = await new_page(wiki.editor, wiki.space_id, "Eigen")
    published = await publish(wiki.editor, own)
    assert (published["status"], published["version"]) == ("published", 2)
    assert published["published_at"] is not None
    foreign = await new_page(wiki.editor2, wiki.space_id, "Fremd")
    r = await wiki.editor.post(f"/api/pages/{foreign['id']}/publish", json={"version": 1})
    assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"
    assert (await publish(wiki.moderator, foreign))["status"] == "published"


async def test_publish_checks_version_and_status(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Doppelt")
    publish_path = f"/api/pages/{page['id']}/publish"
    r = await wiki.editor.post(publish_path, json={"version": 7})
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.version_conflict"
    await publish(wiki.editor, page)
    r = await wiki.editor.post(publish_path, json={"version": 2})
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.already_published"


async def test_removed_member_loses_access_at_once(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Arbeit")
    await SpaceRepository(session).remove_member(
        wiki.space.id, Principal.user(wiki.users["editor"].id)
    )
    for r in (
        await wiki.editor.get(f"/api/pages/{page['id']}"),
        await wiki.editor.patch(f"/api/pages/{page['id']}", json={"title": "x", "version": 1}),
    ):
        assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"


async def test_open_space_pages_are_readable_by_members_not_guests(
    wiki: Wiki, make_space, guest_client: AsyncClient, member_client: AsyncClient
) -> None:
    space: Space = await make_space(SpaceKind.OPEN, "Handbuch")
    page = await publish(wiki.admin, await new_page(wiki.admin, space.id, "Willkommen"))
    assert (await member_client.get(f"/api/pages/{page['id']}")).status_code == 200
    r = await member_client.patch(f"/api/pages/{page['id']}", json={"title": "x", "version": 2})
    assert r.status_code == 403
    assert (await guest_client.get(f"/api/pages/{page['id']}")).status_code == 404


async def test_create_and_publish_are_audited(wiki: Wiki, session: AsyncSession) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Prüfbar"))
    rows = (
        await session.scalars(
            select(AuditLog).where(AuditLog.target_id == page["id"]).order_by(AuditLog.created_at)
        )
    ).all()
    assert [(r.action, r.target_type) for r in rows] == [
        ("page.created", "page"),
        ("page.published", "page"),
    ]
    assert rows[0].details == {"space_id": wiki.space_id, "path": "pruefbar"}
    assert rows[0].actor_id == wiki.users["editor"].id
