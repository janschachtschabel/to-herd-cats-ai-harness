"""Pages whose review is due (plan M7 task 6, decision 11), as the API shows them: the
space's review interval (set by those who manage the space), `reviewed_at` set on
publishing, whether the review is due, "mark as reviewed" and the tree's filter."""

import uuid
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.audit.models import AuditLog
from app.modules.wiki.models import Page
from app.modules.wiki.review_repository import ReviewRepository
from tests.factories_wiki import Wiki, new_page, publish


async def _interval(wiki: Wiki, days: int | None) -> dict[str, Any]:
    space = (await wiki.admin.get(f"/api/spaces/{wiki.space_id}")).json()
    r = await wiki.admin.patch(
        f"/api/spaces/{wiki.space_id}",
        json={"review_interval_days": days, "version": space["version"]},
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


async def _published(wiki: Wiki, title: str, **kw: Any) -> dict[str, Any]:
    return await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, title, **kw))


async def _age(session: AsyncSession, page_id: str, days: int) -> None:
    """The page was last reviewed `days` days ago."""
    at = utcnow() - timedelta(days=days)
    await session.execute(update(Page).where(Page.id == page_id).values(reviewed_at=at))


async def test_those_who_manage_the_space_set_its_review_interval(wiki: Wiki) -> None:
    space = (await wiki.admin.get(f"/api/spaces/{wiki.space_id}")).json()
    assert space["review_interval_days"] is None  # off until someone sets it
    body = await _interval(wiki, 30)
    assert body["review_interval_days"] == 30 and body["version"] == space["version"] + 1
    assert (await _interval(wiki, None))["review_interval_days"] is None
    fresh = (await wiki.moderator.get(f"/api/spaces/{wiki.space_id}")).json()
    r = await wiki.moderator.patch(
        f"/api/spaces/{wiki.space_id}",
        json={"review_interval_days": 30, "version": fresh["version"]},
    )
    assert r.status_code == 403  # moderating pages is not managing the space


async def test_the_review_interval_is_bounded_and_versioned(wiki: Wiki) -> None:
    space = (await wiki.admin.get(f"/api/spaces/{wiki.space_id}")).json()
    for days in (6, 731, 0, -1):
        r = await wiki.admin.patch(
            f"/api/spaces/{wiki.space_id}",
            json={"review_interval_days": days, "version": space["version"]},
        )
        assert r.status_code == 422, (days, r.text)
    for days in (7, 730):
        body = await _interval(wiki, days)
        assert body["review_interval_days"] == days
    r = await wiki.admin.patch(
        f"/api/spaces/{wiki.space_id}",
        json={"review_interval_days": 14, "version": space["version"]},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "spaces.version_conflict"


async def test_the_interval_change_is_audited(wiki: Wiki, session: AsyncSession) -> None:
    await _interval(wiki, 90)
    entry = await session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "space.updated", AuditLog.target_id == wiki.space.id)
        .order_by(AuditLog.id.desc())
    )
    assert entry is not None
    assert entry.details is not None
    assert entry.details["changes"]["review_interval_days"] == {"from": None, "to": 90}


async def test_publishing_sets_reviewed_at(wiki: Wiki) -> None:
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    assert draft["reviewed_at"] is None and draft["review_due"] is False
    page = await publish(wiki.editor, draft)
    assert page["reviewed_at"] == page["published_at"]
    assert page["review_due"] is False


async def test_a_page_is_due_once_its_interval_has_passed(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await _published(wiki, "Zugänge")
    await _age(session, page["id"], 40)
    got = (await wiki.viewer.get(f"/api/pages/{page['id']}")).json()
    assert got["review_due"] is False  # the interval is off
    await _interval(wiki, 30)
    got = (await wiki.viewer.get(f"/api/pages/{page['id']}")).json()
    assert got["review_due"] is True
    await _interval(wiki, 60)
    got = (await wiki.viewer.get(f"/api/pages/{page['id']}")).json()
    assert got["review_due"] is False


async def test_due_counts_whole_utc_days(wiki: Wiki, session: AsyncSession) -> None:
    """Reviewed on day D, a page with 30 days is due from 0:00 UTC of D + 30, whatever
    the hour it was reviewed at."""
    await _interval(wiki, 30)
    page = await _published(wiki, "Tage")
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    late_on_d = today - timedelta(days=30) + timedelta(hours=23, minutes=59)
    await session.execute(update(Page).where(Page.id == page["id"]).values(reviewed_at=late_on_d))
    assert (await wiki.viewer.get(f"/api/pages/{page['id']}")).json()["review_due"] is True
    day_after = today - timedelta(days=29)
    await session.execute(update(Page).where(Page.id == page["id"]).values(reviewed_at=day_after))
    assert (await wiki.viewer.get(f"/api/pages/{page['id']}")).json()["review_due"] is False


async def _tree(client: AsyncClient, wiki: Wiki, **params: Any) -> list[dict[str, Any]]:
    r = await client.get(f"/api/spaces/{wiki.space_id}/pages/tree", params=params)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def test_marking_as_reviewed_starts_the_clock_again(
    wiki: Wiki, session: AsyncSession
) -> None:
    await _interval(wiki, 30)
    page = await _published(wiki, "Alt")
    await _age(session, page["id"], 31)
    before = (await wiki.editor.get(f"/api/pages/{page['id']}")).json()
    assert before["review_due"] is True
    r = await wiki.editor.post(f"/api/pages/{page['id']}/reviewed")
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["review_due"] is False and after["reviewed_at"] > before["reviewed_at"]
    # Nothing of the page changed: neither its version nor when it was last written.
    assert (after["version"], after["updated_at"]) == (before["version"], before["updated_at"])
    entry = await session.scalar(
        select(AuditLog).where(AuditLog.action == "page.reviewed", AuditLog.target_id == page["id"])
    )
    assert entry is not None


async def test_marking_as_reviewed_needs_page_edit_and_a_visible_published_page(
    wiki: Wiki,
) -> None:
    page = await _published(wiki, "Recht")
    r = await wiki.viewer.post(f"/api/pages/{page['id']}/reviewed")
    assert r.status_code == 403
    r = await wiki.outsider.post(f"/api/pages/{page['id']}/reviewed")
    assert r.status_code == 404 and r.json()["error"]["code"] == "page.not_found"
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    r = await wiki.viewer.post(f"/api/pages/{draft['id']}/reviewed")
    assert r.status_code == 404  # a draft the viewer cannot see
    r = await wiki.editor.post(f"/api/pages/{draft['id']}/reviewed")
    assert r.status_code == 409 and r.json()["error"]["code"] == "page.not_published"
    assert (await wiki.moderator.post(f"/api/pages/{page['id']}/reviewed")).status_code == 200


async def test_the_tree_filters_due_pages(wiki: Wiki, session: AsyncSession) -> None:
    old = await _published(wiki, "Alt")
    fresh = await _published(wiki, "Frisch")
    child = await _published(wiki, "Kind", parent_id=old["id"])
    await new_page(wiki.editor, wiki.space_id, "Entwurf")
    trashed = await _published(wiki, "Weg")
    for page in (old, child, trashed):
        await _age(session, page["id"], 100)
    r = await wiki.moderator.post(f"/api/pages/{trashed['id']}/trash", json={"version": 2})
    assert r.status_code == 204, r.text
    assert await _tree(wiki.viewer, wiki, review_due="true") == []  # interval off
    await _interval(wiki, 90)
    due = await _tree(wiki.viewer, wiki, review_due="true")
    assert [n["id"] for n in due] == [old["id"], child["id"]]
    assert all(n["review_due"] for n in due)
    everything = await _tree(wiki.editor, wiki)
    assert {n["id"]: n["review_due"] for n in everything}[fresh["id"]] is False
    assert len(everything) == 4  # the draft too, for an editor
    first = await _tree(wiki.viewer, wiki, review_due="true", limit=1)
    assert [n["id"] for n in first] == [old["id"]]  # paginated like the tree
    r = await wiki.outsider.get(
        f"/api/spaces/{wiki.space_id}/pages/tree", params={"review_due": "true"}
    )
    assert r.status_code == 404  # a team space the outsider cannot see


async def test_marking_as_reviewed_touches_only_its_organisations_page(
    wiki: Wiki, session: AsyncSession
) -> None:
    """Rule 2: the statement itself is scoped by the organisation (review M7 finding 14)."""
    page = await _published(wiki, "Fremd")
    await _age(session, page["id"], 40)
    before = await session.scalar(select(Page.reviewed_at).where(Page.id == page["id"]))
    await ReviewRepository(session).mark_reviewed(uuid.uuid4(), uuid.UUID(page["id"]), utcnow())
    after = await session.scalar(
        select(Page.reviewed_at)
        .where(Page.id == page["id"])
        .execution_options(populate_existing=True)
    )
    assert after == before
