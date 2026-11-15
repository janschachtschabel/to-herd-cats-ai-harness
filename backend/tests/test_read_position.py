"""The read position (plan M9 task 8, M3 N9): `GET /api/conversations/{id}/read` answers
the caller's own position in a conversation she may read (the message she read up to
and when it was written), nothing before she read anything, and like an unknown id for
a conversation she may not see (an admin's inspection included)."""

import uuid
from datetime import datetime

from httpx import AsyncClient

from tests.factories_dms import People, dm_of
from tests.factories_messaging import Chat, post


async def _position(client: AsyncClient, conversation_id: object) -> dict[str, object]:
    response = await client.get(f"/api/conversations/{conversation_id}/read")
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_position_is_the_callers_own_and_moves_forward(chat: Chat) -> None:
    assert await _position(chat.viewer, chat.channel_id) == {
        "last_read_message_id": None,
        "last_read_message_at": None,
    }
    first = await post(chat.viewer2, chat.channel_id, "eins")
    second = await post(chat.viewer2, chat.channel_id, "zwei")
    read = await chat.viewer.post(
        f"/api/conversations/{chat.channel_id}/read", json={"message_id": second["id"]}
    )
    assert read.status_code == 204
    await chat.viewer.post(
        f"/api/conversations/{chat.channel_id}/read", json={"message_id": first["id"]}
    )
    mine = await _position(chat.viewer, chat.channel_id)
    assert mine["last_read_message_id"] == second["id"]
    at = datetime.fromisoformat(str(mine["last_read_message_at"]))
    assert at == datetime.fromisoformat(second["created_at"])
    assert (await _position(chat.viewer2, chat.channel_id))["last_read_message_id"] is None


async def test_a_conversation_one_may_not_see_answers_like_an_unknown_one(
    chat: Chat, people: People
) -> None:
    for client, conversation_id in [
        (chat.outsider, chat.channel_id),
        (chat.viewer, uuid.uuid4()),
    ]:
        response = await client.get(f"/api/conversations/{conversation_id}/read")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation.not_found"
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "Hallo")
    await people.bob.post(f"/api/conversations/{dm['id']}/read", json={"message_id": message["id"]})
    granted = await people.admin.post(
        "/api/admin/dm-inspect", json={"conversation_id": dm["id"], "reason": "Prüfung 4711"}
    )
    assert granted.status_code == 201
    for other in (people.admin, people.carol):
        response = await other.get(f"/api/conversations/{dm['id']}/read")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation.not_found"
    assert (await _position(people.bob, dm["id"]))["last_read_message_id"] == message["id"]
