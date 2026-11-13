"""Reactions (spec 6.1): one emoji per reaction, at most once per person and emoji;
whoever may post in the conversation reacts. Messages show them summed up."""

from urllib.parse import quote

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.messaging.emoji import is_emoji
from tests.factories_dms import People, dm_of
from tests.factories_messaging import Chat, post

THUMBS, HEART = "👍", "❤️"


def _path(message_id: object, emoji: str) -> str:
    return f"/api/messages/{message_id}/reactions/{quote(emoji, safe='')}"


async def _react(client: AsyncClient, message_id: object, emoji: str) -> Response:
    return await client.put(_path(message_id, emoji))


@pytest.mark.parametrize(
    "emoji",
    ["👍", "❤️", "❤", "👍🏽", "🇩🇪", "1️⃣", "#⃣", "👨‍👩‍👧‍👦", "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "🧑🏽‍💻", "🫠"],
)
def test_one_emoji_is_an_emoji(emoji: str) -> None:
    assert is_emoji(emoji)


@pytest.mark.parametrize(
    "text",
    ["", "a", "ab", "👍👍", "👍 ", ":+1:", "🇩", "🇩🇪🇩", "1", "‍", "👍‍", "🏽", "<b>"]
    + ["‍👍", "🏴󠁧󠁢", "1⃣⃣", "👍︎", "👍" + "‍👍" * 20],
)
def test_anything_else_is_not(text: str) -> None:
    assert not is_emoji(text)


async def test_reacting_is_idempotent_and_summed_up(chat: Chat, session: AsyncSession) -> None:
    message = await post(chat.viewer, chat.channel_id, "Abstimmung")
    first = await _react(chat.viewer, message["id"], THUMBS)
    assert first.status_code == 200, first.text
    assert first.json() == [{"emoji": THUMBS, "count": 1, "mine": True}]
    assert (await _react(chat.viewer, message["id"], THUMBS)).json() == first.json()
    await _react(chat.viewer2, message["id"], THUMBS)
    await _react(chat.viewer2, message["id"], HEART)
    listed = (await chat.viewer.get(chat.messages)).json()["items"][0]["reactions"]
    assert listed == [
        {"emoji": THUMBS, "count": 2, "mine": True},
        {"emoji": HEART, "count": 1, "mine": False},
    ]
    removed = await chat.viewer.delete(_path(message["id"], THUMBS))
    assert removed.status_code == 200
    assert removed.json() == [
        {"emoji": THUMBS, "count": 1, "mine": False},
        {"emoji": HEART, "count": 1, "mine": False},
    ]
    assert (await chat.viewer.delete(_path(message["id"], THUMBS))).json() == removed.json()
    events = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == "reaction.changed"))
    ).all()
    assert len(events) == 4  # three added, one removed; repeats change nothing
    assert events[0].payload == {"conversation_id": chat.channel_id, "message_id": message["id"]}


async def test_an_invalid_emoji_is_422(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "x")
    for text in ("a", "👍👍", "Daumen", "%", "👍 "):
        response = await _react(chat.viewer, message["id"], text)
        assert response.status_code == 422, text
        assert response.json()["error"]["code"] == "reaction.invalid_emoji"


async def test_reacting_needs_the_right_to_post(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "x")
    hidden = await _react(chat.outsider, message["id"], THUMBS)
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "message.not_found"
    deleted = await post(chat.viewer, chat.channel_id, "weg")
    await chat.viewer.delete(f"/api/messages/{deleted['id']}")
    gone = await _react(chat.viewer2, deleted["id"], THUMBS)
    assert gone.status_code == 409 and gone.json()["error"]["code"] == "message.deleted"
    await chat.moderator.post(f"/api/conversations/{chat.channel_id}/archive", json={"version": 1})
    archived = await _react(chat.viewer2, message["id"], THUMBS)
    assert archived.status_code == 409
    assert archived.json()["error"]["code"] == "conversation.archived"


async def test_an_inspection_cannot_react(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "Hallo")
    granted = await people.admin.post(
        "/api/admin/dm-inspect", json={"conversation_id": dm["id"], "reason": "Prüfung 4711"}
    )
    assert granted.status_code == 201
    for response in (
        await _react(people.admin, message["id"], THUMBS),
        await people.admin.delete(_path(message["id"], THUMBS)),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "message.not_found"
    assert (await _react(people.bob, message["id"], THUMBS)).status_code == 200
