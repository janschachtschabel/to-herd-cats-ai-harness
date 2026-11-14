"""The daily pass of page review (plan M7 task 6, decision 11) in the test transaction:
`page.review_due` once per interval for each due page (published, outside the trash,
in a space with an interval), in bounded steps; the interval changed; the handler's
timeline entry and the moderators' activity, once however often it is delivered."""

from datetime import datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.core.outbox import Event, EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.groups.models import Group, GroupMember
from app.modules.spaces.models import Space
from app.modules.spaces.repository import SpaceRepository
from app.modules.wiki.events import PAGE_REVIEW_DUE
from app.modules.wiki.models import Page
from app.modules.wiki.review_handlers import notify_on_review_due
from app.modules.wiki.review_pass import review_next
from tests.factories_wiki import Wiki, new_page, publish


async def _interval(session: AsyncSession, wiki: Wiki, days: int | None) -> None:
    space = (await wiki.admin.get(f"/api/spaces/{wiki.space_id}")).json()
    r = await wiki.admin.patch(
        f"/api/spaces/{wiki.space_id}",
        json={"review_interval_days": days, "version": space["version"]},
    )
    assert r.status_code == 200, r.text


async def _published(wiki: Wiki, title: str, **kw: Any) -> dict[str, Any]:
    return await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, title, **kw))


async def _age(session: AsyncSession, page_id: str, days: int) -> None:
    at = utcnow() - timedelta(days=days)
    await session.execute(update(Page).where(Page.id == page_id).values(reviewed_at=at))


async def _pass(session: AsyncSession, now: datetime, batch: int = 100) -> list[int]:
    """Steps until none is left: how many pages each reminded."""
    counts = []
    while (step := await review_next(session, now, batch=batch)) is not None:
        counts.append(step.reminded)
        assert len(counts) < 50
    return counts


async def _events(session: AsyncSession) -> list[EventOutbox]:
    stmt = select(EventOutbox).where(EventOutbox.type == PAGE_REVIEW_DUE).order_by(EventOutbox.id)
    return list((await session.scalars(stmt)).all())


async def _reminded(session: AsyncSession) -> list[str]:
    return [str(e.subject_id) for e in await _events(session)]


async def _handle(session: AsyncSession) -> None:
    for row in await _events(session):
        await notify_on_review_due(session, Event.of(row))


async def _activity(client: AsyncClient) -> list[dict[str, Any]]:
    r = await client.get("/api/activity")
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return [i for i in items if i["reason"] == "review_due"]


async def test_a_due_page_is_reminded_once_per_interval(wiki: Wiki, session: AsyncSession) -> None:
    await _interval(session, wiki, 30)
    old = await _published(wiki, "Alt")
    fresh = await _published(wiki, "Frisch")
    await _age(session, old["id"], 31)
    now = utcnow()
    assert await _pass(session, now) == [1]
    [event] = await _events(session)
    assert (event.subject_type, event.space_id) == ("page", wiki.space.id)
    assert event.payload == {"page_id": old["id"]}  # ids only, never a title
    assert (event.actor_type, event.actor_id) == ("user", wiki.users["editor"].id)
    assert await _pass(session, now + timedelta(hours=3)) == []  # checked today
    assert await _pass(session, now + timedelta(days=1)) == [0]  # a new day: nothing new
    assert await _pass(session, now + timedelta(days=29)) == [0]
    # Unanswered for a whole interval: reminded again (and the fresh page is due now).
    assert await _pass(session, now + timedelta(days=30)) == [2]
    assert sorted(await _reminded(session)) == sorted([old["id"], old["id"], fresh["id"]])


async def test_marking_as_reviewed_starts_the_clock_again(
    wiki: Wiki, session: AsyncSession
) -> None:
    await _interval(session, wiki, 30)
    page = await _published(wiki, "Alt")
    await _age(session, page["id"], 45)
    now = utcnow()
    assert await _pass(session, now) == [1]
    r = await wiki.moderator.post(f"/api/pages/{page['id']}/reviewed")
    assert r.status_code == 200, r.text
    row = await session.scalar(
        select(Page).where(Page.id == page["id"]).execution_options(populate_existing=True)
    )
    assert row is not None and row.review_notified_at is None
    assert await _pass(session, now + timedelta(days=1)) == [0]
    assert await _pass(session, now + timedelta(days=29)) == [0]
    assert await _pass(session, now + timedelta(days=30)) == [1]


async def test_drafts_trash_and_spaces_without_an_interval_are_left_out(
    wiki: Wiki, session: AsyncSession, make_space: Any
) -> None:
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    trashed = await _published(wiki, "Weg")
    kept = await _published(wiki, "Bleibt")
    for page in (draft, trashed, kept):
        await _age(session, page["id"], 400)
    await session.execute(
        update(Page).where(Page.id == draft["id"]).values(reviewed_at=utcnow() - timedelta(400))
    )  # even a draft with an old review time (it cannot have one) is no reminder
    r = await wiki.moderator.post(f"/api/pages/{trashed['id']}/trash", json={"version": 2})
    assert r.status_code == 204, r.text
    other = await make_space("team", "Ohne Frist")
    assert other.review_interval_days is None
    assert await _pass(session, utcnow()) == []  # no space has an interval
    await _interval(session, wiki, 365)
    assert await _pass(session, utcnow()) == [1]
    assert await _reminded(session) == [kept["id"]]


async def test_the_pass_goes_in_bounded_steps(wiki: Wiki, session: AsyncSession) -> None:
    await _interval(session, wiki, 7)
    pages = [await _published(wiki, f"Seite {n}") for n in range(5)]
    for page in pages:
        await _age(session, page["id"], 10)
    now = utcnow()
    first = await review_next(session, now, batch=2)
    assert first is not None and (first.reminded, first.done) == (2, False)
    space = await session.scalar(
        select(Space).where(Space.id == wiki.space.id).execution_options(populate_existing=True)
    )
    assert space is not None and space.review_checked_on is None  # not through yet
    assert await _pass(session, now, batch=2) == [2, 1]
    assert sorted(await _reminded(session)) == sorted(p["id"] for p in pages)


async def test_a_shorter_interval_makes_pages_due_at_the_next_pass(
    wiki: Wiki, session: AsyncSession
) -> None:
    await _interval(session, wiki, 90)
    page = await _published(wiki, "Mittel")
    await _age(session, page["id"], 40)
    now = utcnow()
    assert await _pass(session, now) == [0]  # checked today: nothing due
    await _interval(session, wiki, 30)
    assert await _pass(session, now + timedelta(minutes=5)) == [1]  # the same day
    await _age(session, page["id"], 400)
    await session.execute(update(Page).where(Page.id == page["id"]).values(review_notified_at=None))
    await _interval(session, wiki, None)
    assert await _pass(session, now + timedelta(days=1)) == []  # off: nothing
    assert len(await _events(session)) == 1


async def test_the_moderators_get_one_activity_entry(wiki: Wiki, session: AsyncSession) -> None:
    group = Group(org_id=wiki.space.org_id, name="Redaktion")
    session.add(group)
    await session.flush()
    session.add(
        GroupMember(group_id=group.id, member_type="user", member_id=wiki.users["editor2"].id)
    )
    await SpaceRepository(session).set_member(
        wiki.space.id, Principal.group(group.id), SpaceRole.MODERATOR
    )
    await _interval(session, wiki, 30)
    page = await _published(wiki, "Alt")
    await _age(session, page["id"], 31)
    assert await _pass(session, utcnow()) == [1]
    await _handle(session)
    await _handle(session)  # delivered twice: still one entry each
    for who in ("moderator", "editor2"):
        (entry,) = await _activity(wiki.clients[who])
        assert entry["conversation"]["page_id"] == page["id"]
        assert entry["snippet"] == ""
    for who in ("editor", "viewer", "outsider", "admin"):
        assert await _activity(wiki.clients[who]) == []  # no moderators by membership
    thread = (await wiki.viewer.get(f"/api/pages/{page['id']}/thread")).json()
    r = await wiki.viewer.get(f"/api/conversations/{thread['id']}/messages")
    systems = [m["system"] for m in r.json()["items"] if m["kind"] == "system"]
    assert [s["key"] for s in systems].count(PAGE_REVIEW_DUE) == 1


async def test_nothing_for_a_page_reviewed_or_trashed_before_delivery(
    wiki: Wiki, session: AsyncSession
) -> None:
    await _interval(session, wiki, 30)
    reviewed = await _published(wiki, "Geprüft")
    trashed = await _published(wiki, "Weg")
    for page in (reviewed, trashed):
        await _age(session, page["id"], 31)
    assert await _pass(session, utcnow()) == [2]
    assert (await wiki.editor.post(f"/api/pages/{reviewed['id']}/reviewed")).status_code == 200
    r = await wiki.moderator.post(f"/api/pages/{trashed['id']}/trash", json={"version": 2})
    assert r.status_code == 204, r.text
    await _handle(session)
    assert await _activity(wiki.moderator) == []
