"""Read state and unread counters (spec 6.1, review focus 5): a person's position per
conversation moves only forward; the counters cover only conversations the person
may see at the time of asking, also right after losing access."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from tests.factories_dms import People, dm_of
from tests.factories_messaging import Chat, post

UNREAD = "/api/conversations/unread"


async def _unread(client: AsyncClient) -> dict[str, tuple[int, int]]:
    response = await client.get(UNREAD)
    assert response.status_code == 200, response.text
    return {i["conversation_id"]: (i["unread"], i["mentions"]) for i in response.json()["items"]}


async def _read(client: AsyncClient, conversation_id: object, message_id: object) -> int:
    response = await client.post(
        f"/api/conversations/{conversation_id}/read", json={"message_id": str(message_id)}
    )
    return response.status_code


async def test_others_top_level_messages_count_until_read(chat: Chat) -> None:
    first = await post(chat.viewer, chat.channel_id, "eins")
    second = await post(chat.viewer2, chat.channel_id, "zwei")
    await post(chat.viewer2, chat.channel_id, "Antwort", parent_id=first["id"])
    deleted = await post(chat.viewer2, chat.channel_id, "weg")
    await chat.viewer2.delete(f"/api/messages/{deleted['id']}")
    assert (await _unread(chat.viewer))[chat.channel_id] == (1, 0)
    assert (await _unread(chat.viewer2))[chat.channel_id] == (1, 0)
    assert await _read(chat.viewer, chat.channel_id, second["id"]) == 204
    assert chat.channel_id not in await _unread(chat.viewer)
    assert await _read(chat.viewer, chat.channel_id, first["id"]) == 204  # backwards: no-op
    later = await post(chat.viewer2, chat.channel_id, "drei")
    assert (await _unread(chat.viewer))[chat.channel_id] == (1, 0)
    await _read(chat.viewer, chat.channel_id, later["id"])
    assert chat.channel_id not in await _unread(chat.viewer)


async def test_mentions_count_in_threads_too(chat: Chat) -> None:
    parent = await post(chat.viewer2, chat.channel_id, "Frage")
    await _read(chat.viewer, chat.channel_id, parent["id"])
    reply = await chat.viewer2.post(
        chat.messages,
        json={
            "body_md": "@viewer?",
            "parent_id": parent["id"],
            "mentions": [str(chat.users["viewer"].id)],
        },
    )
    assert reply.status_code == 201
    assert (await _unread(chat.viewer))[chat.channel_id] == (0, 1)
    await _read(chat.viewer, chat.channel_id, reply.json()["id"])
    assert chat.channel_id not in await _unread(chat.viewer)


async def test_moving_forward_is_emitted_for_the_reader_only(
    chat: Chat, session: AsyncSession
) -> None:
    message = await post(chat.viewer2, chat.channel_id, "x")
    for _ in range(2):
        assert await _read(chat.viewer, chat.channel_id, message["id"]) == 204
    events = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == "conversation.read"))
    ).all()
    assert [e.payload for e in events] == [
        {
            "conversation_id": chat.channel_id,
            "message_id": message["id"],
            "user_id": str(chat.users["viewer"].id),
        }
    ]


async def test_only_a_message_of_the_conversation_is_a_position(chat: Chat) -> None:
    other = (
        await chat.moderator.post(f"/api/spaces/{chat.space.id}/channels", json={"name": "zwei"})
    ).json()
    elsewhere = await post(chat.viewer, other["id"], "anderswo")
    for message_id in (elsewhere["id"], uuid.uuid4()):
        response = await chat.viewer.post(
            f"/api/conversations/{chat.channel_id}/read", json={"message_id": str(message_id)}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "message.not_found"
    message = await post(chat.viewer, chat.channel_id, "x")
    hidden = await chat.outsider.post(
        f"/api/conversations/{chat.channel_id}/read", json={"message_id": message["id"]}
    )
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "conversation.not_found"


async def test_counters_forget_a_conversation_once_access_is_gone(chat: Chat) -> None:
    await post(chat.viewer, chat.channel_id, "eins")
    mention = await chat.viewer.post(
        chat.messages, json={"body_md": "@v2", "mentions": [str(chat.users["viewer2"].id)]}
    )
    assert mention.status_code == 201
    assert (await _unread(chat.viewer2))[chat.channel_id] == (2, 1)
    removed = await chat.admin.delete(
        f"/api/spaces/{chat.space.id}/members/user/{chat.users['viewer2'].id}"
    )
    assert removed.status_code == 204, removed.text
    assert await _unread(chat.viewer2) == {}


async def test_dms_count_for_their_participants_only(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    await post(people.alice, dm["id"], "psst")
    assert (await _unread(people.bob))[dm["id"]] == (1, 0)
    for other in (people.carol, people.admin):
        assert dm["id"] not in await _unread(other)


async def test_an_inspection_cannot_mark_as_read(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "Hallo")
    granted = await people.admin.post(
        "/api/admin/dm-inspect", json={"conversation_id": dm["id"], "reason": "Prüfung 4711"}
    )
    assert granted.status_code == 201
    response = await people.admin.post(
        f"/api/conversations/{dm['id']}/read", json={"message_id": message["id"]}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation.not_found"


async def test_the_counters_are_paged(chat: Chat) -> None:
    second = (
        await chat.moderator.post(f"/api/spaces/{chat.space.id}/channels", json={"name": "zwei"})
    ).json()
    await post(chat.viewer2, chat.channel_id, "a")
    await post(chat.viewer2, second["id"], "b")
    first = (await chat.viewer.get(UNREAD, params={"limit": 1})).json()
    rest = (await chat.viewer.get(UNREAD, params={"cursor": first["next_cursor"]})).json()
    seen = [i["conversation_id"] for i in first["items"] + rest["items"]]
    assert sorted(seen) == sorted([chat.channel_id, second["id"]])
    assert rest["next_cursor"] is None
