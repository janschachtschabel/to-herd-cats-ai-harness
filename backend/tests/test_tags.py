"""Tags: one shared pool per organisation, system-wide or per space, on pages (plan M2
task 4)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import AuditLog
from app.modules.orgs.models import Organization
from app.modules.tags.models import Tagging
from app.modules.tags.service import TagService
from app.modules.wiki.models import Page
from tests.factories_wiki import Wiki, new_page, publish


async def _tag(client: AsyncClient, name: str, space_id: object = None, **extra: Any) -> Any:
    body: dict[str, Any] = {"name": name, **extra}
    if space_id is not None:
        body["space_id"] = str(space_id)
    return await client.post("/api/tags", json=body)


async def _made(client: AsyncClient, name: str, space_id: object = None) -> dict[str, Any]:
    r = await _tag(client, name, space_id)
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def _set(client: AsyncClient, page: dict[str, Any], *tags: dict[str, Any]) -> Any:
    fresh = (await client.get(f"/api/pages/{page['id']}")).json()
    body = {"tag_ids": [t["id"] for t in tags], "version": fresh["version"]}
    return await client.put(f"/api/pages/{page['id']}/tags", json=body)


async def _names(client: AsyncClient, **params: Any) -> list[str]:
    r = await client.get("/api/tags", params=params)
    assert r.status_code == 200, r.text
    return [t["name"] for t in r.json()["items"]]


def _error(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code


async def test_admin_creates_system_tags_moderator_space_tags(wiki: Wiki) -> None:
    r = await _tag(wiki.admin, "Wichtig", color="#FF0000")
    assert r.status_code == 201, r.text
    assert {k: r.json()[k] for k in ("name", "color", "space_id", "version")} == {
        "name": "Wichtig",
        "color": "#ff0000",
        "space_id": None,
        "version": 1,
    }
    _error(await _tag(wiki.moderator, "Global"), 403, "auth.permission_denied")
    assert (await _tag(wiki.moderator, "Team", wiki.space_id)).status_code == 201
    _error(await _tag(wiki.editor, "Autor", wiki.space_id), 403, "auth.permission_denied")
    _error(await _tag(wiki.outsider, "Fremd", wiki.space_id), 404, "space.not_found")
    _error(await _tag(wiki.admin, "Farbe", color="red"), 422, "validation_failed")


async def test_duplicate_name_in_scope_is_409_case_insensitive(wiki: Wiki) -> None:
    await _made(wiki.admin, "Wichtig")
    _error(await _tag(wiki.admin, "wichtig"), 409, "tags.name_taken")
    # The same name in a space is another scope.
    space_tag = await _made(wiki.moderator, "WICHTIG", wiki.space_id)
    _error(await _tag(wiki.moderator, "Wichtig", wiki.space_id), 409, "tags.name_taken")
    other = await _made(wiki.moderator, "Anders", wiki.space_id)
    r = await wiki.moderator.patch(
        f"/api/tags/{other['id']}", json={"name": "wichtig", "version": 1}
    )
    _error(r, 409, "tags.name_taken")
    r = await wiki.moderator.patch(
        f"/api/tags/{space_tag['id']}", json={"name": "Wichtig!", "color": "#00aa00", "version": 1}
    )
    assert r.status_code == 200 and (r.json()["name"], r.json()["version"]) == ("Wichtig!", 2)
    r = await wiki.moderator.patch(f"/api/tags/{space_tag['id']}", json={"name": "x", "version": 1})
    _error(r, 409, "tags.version_conflict")


async def test_member_does_not_see_tags_of_invisible_space(
    wiki: Wiki, make_space, member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    await _made(wiki.admin, "System")
    secret = await _made(wiki.moderator, "Geheim", wiki.space_id)
    open_space = await make_space("open", "Handbuch")
    await _made(wiki.admin, "Offen", open_space.id)
    assert await _names(wiki.viewer) == ["Geheim", "Offen", "System"]
    assert await _names(member_client) == ["Offen", "System"]
    assert await _names(guest_client) == ["System"]
    assert await _names(wiki.viewer, space_id=wiki.space_id) == ["Geheim", "System"]
    r = await member_client.get("/api/tags", params={"space_id": wiki.space_id})
    _error(r, 404, "space.not_found")
    for r in (
        await member_client.patch(f"/api/tags/{secret['id']}", json={"name": "x", "version": 1}),
        await member_client.delete(f"/api/tags/{secret['id']}"),
    ):
        _error(r, 404, "tags.not_found")
    # A viewer sees the tag but may not change it.
    _error(await wiki.viewer.delete(f"/api/tags/{secret['id']}"), 403, "auth.permission_denied")


async def test_tags_of_another_organisation_are_invisible(
    wiki: Wiki, session: AsyncSession, make_user
) -> None:
    elsewhere = Organization(name="Elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user("owner", organization=elsewhere)
    actor = Actor(elsewhere.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    foreign = await TagService(session).create(actor, "Fremd", "#000000")
    assert await _names(wiki.admin) == []
    _error(await wiki.admin.delete(f"/api/tags/{foreign.id}"), 404, "tags.not_found")
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    _error(await _set(wiki.editor, page, {"id": str(foreign.id)}), 422, "tags.not_found")


async def test_system_filter_lists_only_system_wide_tags(wiki: Wiki) -> None:
    for name in ("Beta", "Alpha"):
        await _made(wiki.admin, name)
    await _made(wiki.moderator, "Team", wiki.space_id)
    assert await _names(wiki.admin) == ["Alpha", "Beta", "Team"]
    assert await _names(wiki.admin, system="true") == ["Alpha", "Beta"]
    page = (await wiki.admin.get("/api/tags", params={"system": "true", "limit": 1})).json()
    rest = await wiki.admin.get(
        "/api/tags", params={"system": "true", "limit": 1, "cursor": page["next_cursor"]}
    )
    assert [t["name"] for t in rest.json()["items"]] == ["Beta"]
    r = await wiki.admin.get("/api/tags", params={"system": "true", "space_id": wiki.space_id})
    _error(r, 422, "validation_failed")


async def test_tag_list_is_sorted_by_name_and_paginated(wiki: Wiki) -> None:
    for name in ("delta", "Alpha", "charlie", "Bravo"):
        await _made(wiki.admin, name)
    first = (await wiki.viewer.get("/api/tags", params={"limit": 3})).json()
    assert [t["name"] for t in first["items"]] == ["Alpha", "Bravo", "charlie"]
    rest = await wiki.viewer.get("/api/tags", params={"limit": 3, "cursor": first["next_cursor"]})
    assert [t["name"] for t in rest.json()["items"]] == ["delta"]
    assert rest.json()["next_cursor"] is None


async def test_editor_sets_page_tags_and_page_and_tree_carry_them(wiki: Wiki) -> None:
    system = await _made(wiki.admin, "System")
    team = await _made(wiki.moderator, "Team", wiki.space_id)
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    r = await _set(wiki.editor, page, system, team, team)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["tags"]) == sorted([system["id"], team["id"]])
    assert r.json()["version"] == 2
    got = (await wiki.editor.get(f"/api/pages/{page['id']}")).json()
    assert sorted(got["tags"]) == sorted([system["id"], team["id"]])
    tree = (await wiki.editor.get(f"/api/spaces/{wiki.space_id}/pages/tree")).json()
    assert sorted(tree["items"][0]["tags"]) == sorted([system["id"], team["id"]])
    r = await _set(wiki.editor, page)
    assert r.status_code == 200 and r.json()["tags"] == []
    # A stale page version is a conflict; a viewer may not tag.
    r = await wiki.editor.put(f"/api/pages/{page['id']}/tags", json={"tag_ids": [], "version": 1})
    _error(r, 409, "page.version_conflict")
    published = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Fertig"))
    _error(await _set(wiki.viewer, published, system), 403, "auth.permission_denied")


async def test_space_tag_cannot_be_put_on_page_of_other_space(wiki: Wiki, make_space) -> None:
    other = await make_space("team", "Anders", members=[(wiki.users["moderator"], "moderator")])
    foreign = await _made(wiki.moderator, "Anders", other.id)
    page = await new_page(wiki.moderator, wiki.space_id, "Seite")
    _error(await _set(wiki.moderator, page, foreign), 422, "tags.wrong_space")
    # Someone who cannot see that space learns nothing about the tag.
    _error(await _set(wiki.editor, page, foreign), 422, "tags.not_found")
    _error(await _set(wiki.editor, page, {"id": str(uuid7())}), 422, "tags.not_found")


async def test_deleting_tag_removes_taggings(wiki: Wiki, session: AsyncSession) -> None:
    tag = await _made(wiki.moderator, "Weg", wiki.space_id)
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    assert (await _set(wiki.editor, page, tag)).status_code == 200
    assert (await wiki.moderator.delete(f"/api/tags/{tag['id']}")).status_code == 204
    assert (await wiki.editor.get(f"/api/pages/{page['id']}")).json()["tags"] == []
    count = await session.scalar(select(func.count()).select_from(Tagging))
    assert count == 0
    _error(await wiki.moderator.delete(f"/api/tags/{tag['id']}"), 404, "tags.not_found")


async def test_purging_a_page_removes_its_taggings(wiki: Wiki, session: AsyncSession) -> None:
    tag = await _made(wiki.admin, "Bleibt")
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=page["id"])
    assert (await _set(wiki.editor, page, tag)).status_code == 200
    assert (await _set(wiki.editor, child, tag)).status_code == 200
    fresh = (await wiki.editor.get(f"/api/pages/{page['id']}")).json()
    r = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": fresh["version"]}
    )
    assert r.status_code == 204
    assert (await wiki.admin.delete(f"/api/pages/{page['id']}")).status_code == 204
    assert await session.scalar(select(func.count()).select_from(Tagging)) == 0
    assert await session.scalar(select(func.count()).select_from(Page)) == 0


async def test_tree_filter_by_tag(wiki: Wiki) -> None:
    tag = await _made(wiki.admin, "Filter")
    a = await new_page(wiki.editor, wiki.space_id, "A")
    b = await new_page(wiki.editor, wiki.space_id, "B", parent_id=a["id"])
    await new_page(wiki.editor, wiki.space_id, "C")
    await _set(wiki.editor, b, tag)
    tree = f"/api/spaces/{wiki.space_id}/pages/tree"
    r = await wiki.editor.get(tree, params={"tag": tag["id"]})
    assert [n["id"] for n in r.json()["items"]] == [b["id"]]
    r = await wiki.editor.get(tree, params={"tag": str(uuid7())})
    assert r.status_code == 200 and r.json()["items"] == []


async def test_tag_changes_are_audited(wiki: Wiki, session: AsyncSession) -> None:
    tag = await _made(wiki.admin, "Prüfbar")
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    await _set(wiki.editor, page, tag)
    await wiki.admin.patch(f"/api/tags/{tag['id']}", json={"color": "#123456", "version": 1})
    await wiki.admin.delete(f"/api/tags/{tag['id']}")
    actions = (await session.scalars(select(AuditLog.action).order_by(AuditLog.id))).all()
    assert [a for a in actions if a.startswith("tag") or a == "page.tags_set"] == [
        "tag.created",
        "page.tags_set",
        "tag.updated",
        "tag.deleted",
    ]
