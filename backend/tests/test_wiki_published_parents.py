"""Every ancestor of a published page is published (ruling on M2 tasks 1-3).

Publishing under a draft, moving published pages under a draft and restoring them
under a draft answer 409 `page.parent_draft`; so a viewer, who sees only published
pages, never sees a page whose parent they cannot see.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wiki.models import Page, PageStatus
from tests.factories_wiki import Wiki, new_page, publish


async def _get(client: AsyncClient, page: dict[str, Any]) -> dict[str, Any]:
    r = await client.get(f"/api/pages/{page['id']}")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


async def _move(client: AsyncClient, page: dict[str, Any], parent: dict[str, Any] | None) -> Any:
    fresh = await _get(client, page)
    body = {"parent_id": parent["id"] if parent else None, "version": fresh["version"]}
    return await client.post(f"/api/pages/{page['id']}/move", json=body)


def _parent_draft(r: Any) -> None:
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "page.parent_draft"


async def test_publish_under_a_draft_parent_is_409(wiki: Wiki) -> None:
    parent = await new_page(wiki.editor, wiki.space_id, "Eltern")
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=parent["id"])
    r = await wiki.moderator.post(f"/api/pages/{child['id']}/publish", json={"version": 1})
    _parent_draft(r)
    await publish(wiki.editor, parent)
    assert (await publish(wiki.editor, child))["status"] == "published"


async def test_moving_a_published_page_under_a_draft_is_409(wiki: Wiki) -> None:
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    done = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Fertig"))
    _parent_draft(await _move(wiki.editor, done, draft))
    # A draft may go under a draft; a published page under a published one.
    other = await new_page(wiki.editor, wiki.space_id, "Notiz")
    assert (await _move(wiki.editor, other, draft)).status_code == 200
    target = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Ziel"))
    assert (await _move(wiki.editor, done, target)).status_code == 200


async def test_moving_a_subtree_with_a_published_page_under_a_draft_is_409(
    wiki: Wiki, session: AsyncSession
) -> None:
    root = await new_page(wiki.editor, wiki.space_id, "Wurzel")
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=root["id"])
    # Only data from before the rule can hold a published page below a draft.
    await session.execute(
        update(Page).where(Page.id == child["id"]).values(status=PageStatus.PUBLISHED)
    )
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    _parent_draft(await _move(wiki.editor, root, draft))


async def test_restore_under_a_draft_parent_is_409(wiki: Wiki, session: AsyncSession) -> None:
    parent = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Eltern"))
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=parent["id"])
    child = await publish(wiki.editor, child)
    r = await wiki.moderator.post(
        f"/api/pages/{child['id']}/trash", json={"version": child["version"]}
    )
    assert r.status_code == 204
    # No operation turns a published page back into a draft; data from before can.
    await session.execute(
        update(Page).where(Page.id == parent["id"]).values(status=PageStatus.DRAFT)
    )
    _parent_draft(await wiki.moderator.post(f"/api/pages/{child['id']}/restore"))
    await session.execute(
        update(Page).where(Page.id == parent["id"]).values(status=PageStatus.PUBLISHED)
    )
    r = await wiki.moderator.post(f"/api/pages/{child['id']}/restore")
    assert r.status_code == 200 and r.json()["parent_id"] == parent["id"]


async def test_a_viewer_never_sees_a_page_whose_parent_they_cannot_see(wiki: Wiki) -> None:
    a = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "A"))
    b = await new_page(wiki.editor, wiki.space_id, "B")
    a1 = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "A1", parent_id=a["id"])
    )
    b1 = await new_page(wiki.editor, wiki.space_id, "B1", parent_id=b["id"])
    a2 = await new_page(wiki.editor, wiki.space_id, "A2", parent_id=a["id"])
    # Every way to get a published page below a draft is refused.
    _parent_draft(await wiki.moderator.post(f"/api/pages/{b1['id']}/publish", json={"version": 1}))
    _parent_draft(await _move(wiki.editor, a, b))
    _parent_draft(await _move(wiki.editor, a1, b))
    _parent_draft(await _move(wiki.editor, a1, a2))
    assert (await _move(wiki.editor, a2, b1)).status_code == 200

    tree = await wiki.viewer.get(f"/api/spaces/{wiki.space_id}/pages/tree", params={"limit": 100})
    nodes = tree.json()["items"]
    seen = {n["id"] for n in nodes}
    assert seen == {a["id"], a1["id"]}
    assert all(n["parent_id"] is None or n["parent_id"] in seen for n in nodes)
    for n in nodes:  # and each page the viewer can open has a parent it can open
        page = await _get(wiki.viewer, n)
        if page["parent_id"] is not None:
            assert (await wiki.viewer.get(f"/api/pages/{page['parent_id']}")).status_code == 200
