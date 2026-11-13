"""Mentions (plan decision 4, review focus 4): structured ids next to the text. Only
people who may see the conversation are stored; every other id asked for comes back
in `not_notified`, and an unknown id cannot be told apart from one without access."""

import uuid
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.social_models import MessageMention
from app.modules.orgs.models import Organization
from tests.factories_dms import People, dm_of
from tests.factories_messaging import Chat, post


async def _send(
    client: AsyncClient, conversation_id: object, mentions: list[Any], **extra: Any
) -> Response:
    body = {"body_md": "Hallo @[Jemand](user:x)", "mentions": [str(m) for m in mentions], **extra}
    return await client.post(f"/api/conversations/{conversation_id}/messages", json=body)


async def _stored(session: AsyncSession, message_id: object) -> set[uuid.UUID]:
    rows = await session.scalars(
        select(MessageMention.user_id).where(
            MessageMention.message_id == uuid.UUID(str(message_id))
        )
    )
    return set(rows)


async def test_only_people_who_see_the_conversation_are_mentioned(
    chat: Chat, make_user, session: AsyncSession
) -> None:
    elsewhere = Organization(name="Andere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user(organization=elsewhere)
    inactive = await make_user(name="Weg", is_active=False)
    unknown = uuid.uuid4()
    ids = {name: chat.users[name].id for name in ("viewer", "viewer2", "outsider", "admin")}
    asked = [
        ids["viewer2"],
        ids["outsider"],
        unknown,
        ids["viewer2"],
        stranger.id,
        inactive.id,
        ids["viewer"],  # oneself
        ids["admin"],  # sees every space
    ]
    response = await _send(chat.viewer, chat.channel_id, asked)
    assert response.status_code == 201, response.text
    message = response.json()
    assert message["not_notified"] == [
        str(ids["outsider"]),
        str(unknown),
        str(stranger.id),
        str(inactive.id),
    ]
    expected = {ids["viewer2"], ids["viewer"], ids["admin"]}
    assert set(map(uuid.UUID, message["mentions"])) == expected
    assert await _stored(session, message["id"]) == expected
    listed = (await chat.viewer2.get(chat.messages)).json()["items"]
    assert set(map(uuid.UUID, listed[0]["mentions"])) == expected


async def test_unknown_ids_and_ids_without_access_read_the_same(
    chat: Chat, session: AsyncSession
) -> None:
    outsider, unknown = chat.users["outsider"].id, uuid.uuid4()
    no_access = await _send(chat.viewer, chat.channel_id, [outsider])
    nobody = await _send(chat.viewer, chat.channel_id, [unknown])
    assert no_access.status_code == nobody.status_code == 201

    def shape(response: Response, asked: uuid.UUID) -> dict[str, Any]:
        body = response.json()
        assert body.pop("not_notified") == [str(asked)]
        return {k: v for k, v in body.items() if k not in ("id", "created_at")}

    assert shape(no_access, outsider) == shape(nobody, unknown)
    for response in (no_access, nobody):
        assert await _stored(session, response.json()["id"]) == set()


async def test_mentions_are_bounded(chat: Chat) -> None:
    many = [uuid.uuid4() for _ in range(51)]
    assert (await _send(chat.viewer, chat.channel_id, many)).status_code == 422
    assert (await _send(chat.viewer, chat.channel_id, many[:50])).status_code == 201


async def test_editing_replaces_the_mentions_when_given(chat: Chat) -> None:
    first = await _send(chat.viewer, chat.channel_id, [chat.users["viewer2"].id])
    path = f"/api/messages/{first.json()['id']}"
    unchanged = await chat.viewer.patch(path, json={"body_md": "neu"})
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["mentions"] == [str(chat.users["viewer2"].id)]
    assert unchanged.json()["not_notified"] == []
    outsider = chat.users["outsider"].id
    changed = await chat.viewer.patch(
        path, json={"body_md": "anders", "mentions": [str(chat.users["editor"].id), str(outsider)]}
    )
    assert changed.json()["mentions"] == [str(chat.users["editor"].id)]
    assert changed.json()["not_notified"] == [str(outsider)]


async def test_a_resend_answers_like_the_first_send(chat: Chat) -> None:
    client_id = str(uuid.uuid4())
    asked = [chat.users["viewer2"].id, chat.users["outsider"].id]
    first = await _send(chat.viewer, chat.channel_id, asked, client_id=client_id)
    again = await _send(chat.viewer, chat.channel_id, asked, client_id=client_id)
    assert (first.status_code, again.status_code) == (201, 200)
    for key in ("id", "mentions", "not_notified"):
        assert first.json()[key] == again.json()[key]


async def test_in_a_dm_only_participants_are_mentioned(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    response = await _send(people.alice, dm["id"], [people.id("bob"), people.id("carol")])
    assert response.json()["mentions"] == [people.id("bob")]
    assert response.json()["not_notified"] == [people.id("carol")]


async def test_plain_messages_have_no_mentions(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "ohne")
    assert (message["mentions"], message["not_notified"], message["reactions"]) == ([], [], [])
