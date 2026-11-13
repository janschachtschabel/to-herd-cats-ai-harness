"""Search in messages (plan M3 task 9, review focus 5). The visibility filter is part
of the one statement for every kind of conversation: channels through the spaces one
may read, DMs through taking part (never through an admin's inspection), page threads
through the page's visibility. Deleted and system messages are never found."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.threads import page_timeline
from tests.factories_dms import People, dm_of
from tests.factories_messaging import Chat, post
from tests.factories_wiki import Wiki, new_page, publish

WORD = "Quittungsblock"


async def search(client: AsyncClient, q: str = WORD, **params: Any) -> list[dict[str, Any]]:
    response = await client.get("/api/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def message_ids(client: AsyncClient, q: str = WORD, **params: Any) -> list[str]:
    return [h["id"] for h in await search(client, q, **params) if h["type"] == "message"]


async def test_a_channel_message_is_found_by_the_space_readers_only(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, f"Wo ist der {WORD}?")
    (hit,) = await search(chat.viewer2)
    assert hit["type"] == "message" and hit["id"] == message["id"]
    assert hit["conversation"] == {
        "id": chat.channel_id,
        "kind": "channel",
        "name": "plaudern",
        "space_id": str(chat.space.id),
        "page_id": None,
        "ticket_number": None,
    }
    assert hit["author"] == {
        "type": "user",
        "id": str(chat.users["viewer"].id),
        "name": "Chat viewer",
    }
    assert "⟦" in hit["snippet"] and hit["parent_id"] is None and hit["created_at"]
    assert await message_ids(chat.outsider) == []


async def test_a_removed_member_no_longer_finds_the_channel(chat: Chat) -> None:
    await post(chat.viewer, chat.channel_id, WORD)
    assert len(await message_ids(chat.viewer2)) == 1
    viewer2 = chat.users["viewer2"].id
    removed = await chat.admin.delete(f"/api/spaces/{chat.space.id}/members/user/{viewer2}")
    assert removed.status_code == 204, removed.text
    assert await message_ids(chat.viewer2) == []


async def test_dm_messages_only_for_participants_never_for_an_inspection(
    people: People,
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], f"Der {WORD} liegt bei mir")
    assert await message_ids(people.bob) == [message["id"]]
    assert await message_ids(people.carol) == []
    inspection = await people.admin.post(
        "/api/admin/dm-inspect",
        json={"conversation_id": dm["id"], "reason": "a reason that is long enough"},
    )
    assert inspection.status_code == 201
    assert await message_ids(people.admin) == []


async def test_page_thread_messages_follow_the_page(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    thread = (await wiki.editor.get(f"/api/pages/{page['id']}/thread")).json()
    message = await post(wiki.editor, thread["id"], f"{WORD} im Entwurf")
    assert await message_ids(wiki.editor2) == [message["id"]]
    assert await message_ids(wiki.viewer) == []  # a draft
    page = await publish(wiki.editor, page)
    (hit,) = [h for h in await search(wiki.viewer) if h["type"] == "message"]
    assert hit["conversation"]["page_id"] == page["id"]
    assert hit["conversation"]["kind"] == "thread_page"
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert trashed.status_code == 204
    assert await message_ids(wiki.editor) == []


async def test_deleted_and_system_messages_are_never_found(
    wiki: Wiki, chat: Chat, session: AsyncSession
) -> None:
    message = await post(chat.viewer, chat.channel_id, WORD)
    assert (await chat.viewer.delete(f"/api/messages/{message['id']}")).status_code == 204
    assert await message_ids(chat.viewer) == []
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    for row in (await session.scalars(select(EventOutbox))).all():
        if row.type.startswith("page."):
            await page_timeline(session, Event.of(row))
    # A system message's body is JSON: its words `key`, `actor` and the event's name.
    for word in ("key", "actor", "page.published"):
        assert await message_ids(wiki.editor, word) == []
    assert page["id"]


async def test_types_space_and_tags(wiki: Wiki, chat: Chat) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, WORD))
    message = await post(chat.moderator, chat.channel_id, WORD)
    dm = await dm_of(chat.moderator, chat.users["viewer"].id)
    in_dm = await post(chat.moderator, dm["id"], WORD)
    # A system admin reads every space, but no DM it does not take part in.
    assert {h["id"] for h in await search(chat.admin)} == {page["id"], message["id"]}
    assert {h["id"] for h in await search(chat.moderator)} == {message["id"], in_dm["id"]}
    in_space = await search(chat.moderator, space_id=str(chat.space.id))
    assert [h["id"] for h in in_space] == [message["id"]]  # its channels and threads only
    assert await search(chat.moderator, types="page") == []
    assert [h["id"] for h in await search(chat.admin, types="message")] == [message["id"]]
    assert [h["id"] for h in await search(chat.admin, types="page")] == [page["id"]]
    tag = await wiki.admin.post("/api/tags", json={"name": "t"})
    assert tag.status_code == 201, tag.text
    assert await search(chat.admin, tag=tag.json()["id"]) == []  # messages carry no tags
    bad = await chat.admin.get("/api/search", params={"q": WORD, "types": "page,ticket"})
    assert bad.status_code == 422


async def test_pages_and_messages_share_one_ranking_and_cursor(wiki: Wiki) -> None:
    thread_page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Ort"))
    thread = (await wiki.editor.get(f"/api/pages/{thread_page['id']}/thread")).json()
    expected = set()
    for i in range(3):
        page = await publish(
            wiki.editor, await new_page(wiki.editor, wiki.space_id, f"Seite {i}", content_md=WORD)
        )
        expected.add(page["id"])
        expected.add((await post(wiki.editor, thread["id"], f"{WORD} {i}"))["id"])
    seen: list[dict[str, Any]] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"q": WORD, "limit": 2}
        if cursor:
            params["cursor"] = cursor
        body = (await wiki.viewer.get("/api/search", params=params)).json()
        seen.extend(body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert {h["id"] for h in seen} == expected and len(seen) == 6
    scores = [h["score"] for h in seen]
    assert scores == sorted(scores, reverse=True)
