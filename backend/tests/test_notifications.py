"""Notifications and the activity view (spec 6.1, 6.2; review focus 2, 4, 5).

The handler `notify_on_message` runs here in the test's transaction, as the worker
would run it, and more than once where that matters: its effect is the same.
"""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.notifications import notify_on_message
from tests.factories_dms import People, dm_of
from tests.factories_messaging import Chat, post

ACTIVITY = "/api/activity"


async def deliver(session: AsyncSession) -> None:
    """Hand every message event so far to the handler (again, if it had them)."""
    rows = await session.scalars(
        select(EventOutbox)
        .where(EventOutbox.type.in_(("message.created", "message.updated")))
        .order_by(EventOutbox.id)
    )
    for row in rows.all():
        await notify_on_message(session, Event.of(row))


async def mention(chat: Chat, author: str, *names: str, **extra: Any) -> dict[str, Any]:
    body = {
        "body_md": "Schau mal @[x](user:x)",
        "mentions": [str(chat.users[n].id) for n in names],
        **extra,
    }
    response = await chat.clients[author].post(chat.messages, json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


async def entries(client: AsyncClient, **params: Any) -> list[dict[str, Any]]:
    response = await client.get(ACTIVITY, params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


async def _count(session: AsyncSession, type_: str) -> int:
    stmt = select(func.count()).select_from(EventOutbox).where(EventOutbox.type == type_)
    return int(await session.scalar(stmt) or 0)


async def test_a_mention_notifies_exactly_once(chat: Chat, session: AsyncSession) -> None:
    message = await mention(chat, "viewer", "viewer2")
    for _ in range(3):
        await deliver(session)
    (entry,) = await entries(chat.viewer2)
    assert entry["reason"] == "mention" and entry["message_id"] == message["id"]
    assert entry["conversation"] == {
        "id": chat.channel_id,
        "kind": "channel",
        "name": "plaudern",
        "space_id": str(chat.space.id),
        "page_id": None,
    }
    assert entry["author"] == {
        "type": "user",
        "id": str(chat.users["viewer"].id),
        "name": "Chat viewer",
    }
    assert entry["snippet"] == "Schau mal @[x](user:x)" and entry["parent_id"] is None
    assert (entry["read_at"], entry["done_at"]) == (None, None)
    assert await _count(session, "notification.created") == 1
    created = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == "notification.created"))
    ).one()
    assert created.payload == {
        "notification_id": entry["id"],
        "conversation_id": chat.channel_id,
        "message_id": message["id"],
        "user_id": str(chat.users["viewer2"].id),
    }


async def test_nobody_is_notified_of_their_own_message(chat: Chat, session: AsyncSession) -> None:
    top = await mention(chat, "viewer", "viewer")
    await post(chat.viewer, chat.channel_id, "selbst", parent_id=top["id"])
    await deliver(session)
    assert await entries(chat.viewer) == []


async def test_a_reply_notifies_who_wrote_in_the_thread_before(
    chat: Chat, session: AsyncSession
) -> None:
    top = await post(chat.viewer, chat.channel_id, "Frage")
    await post(chat.viewer2, chat.channel_id, "erste", parent_id=top["id"])
    await deliver(session)
    second = await mention(chat, "editor", "viewer2", parent_id=top["id"])
    await deliver(session)
    await post(chat.moderator, chat.channel_id, "später", parent_id=top["id"])
    await deliver(session)
    reasons = {
        name: sorted((e["reason"], e["parent_id"]) for e in await entries(chat.clients[name]))
        for name in ("viewer", "viewer2", "editor", "moderator")
    }
    assert reasons == {
        "viewer": [("reply", top["id"])] * 3,
        "viewer2": [("mention", top["id"]), ("reply", top["id"])],
        "editor": [("reply", top["id"])],
        "moderator": [],
    }
    viewer2 = await entries(chat.viewer2)
    assert next(e for e in viewer2 if e["reason"] == "mention")["message_id"] == second["id"]


async def test_access_is_checked_again_at_delivery(chat: Chat, session: AsyncSession) -> None:
    await mention(chat, "viewer", "viewer2")
    removed = await chat.admin.delete(
        f"/api/spaces/{chat.space.id}/members/user/{chat.users['viewer2'].id}"
    )
    assert removed.status_code == 204
    await deliver(session)
    stored = await session.scalar(select(func.count()).select_from(Notification))
    assert stored == 0


async def test_entries_go_once_their_conversation_is_out_of_sight(
    chat: Chat, session: AsyncSession
) -> None:
    await mention(chat, "viewer", "viewer2")
    await deliver(session)
    (entry,) = await entries(chat.viewer2)
    await chat.admin.delete(f"/api/spaces/{chat.space.id}/members/user/{chat.users['viewer2'].id}")
    assert await entries(chat.viewer2, include_done=True) == []
    assert (await chat.viewer2.get(f"{ACTIVITY}/count")).json() == {"open": 0, "unread": 0}
    for action in ("read", "done"):
        response = await chat.viewer2.post(f"{ACTIVITY}/{entry['id']}/{action}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "notification.not_found"


async def test_someone_elses_notification_is_404(chat: Chat, session: AsyncSession) -> None:
    await mention(chat, "viewer", "viewer2")
    await deliver(session)
    (entry,) = await entries(chat.viewer2)
    for client in (chat.viewer, chat.admin):
        for action in ("read", "done"):
            response = await client.post(f"{ACTIVITY}/{entry['id']}/{action}")
            assert response.status_code == 404
    unknown = await chat.viewer2.post(f"{ACTIVITY}/{uuid.uuid4()}/read")
    assert unknown.status_code == 404


async def test_reading_and_finishing(chat: Chat, session: AsyncSession) -> None:
    for _ in range(3):
        await mention(chat, "viewer", "viewer2")
    await deliver(session)
    newest, middle, oldest = await entries(chat.viewer2)
    count = f"{ACTIVITY}/count"
    assert (await chat.viewer2.get(count)).json() == {"open": 3, "unread": 3}
    for _ in range(2):
        assert (await chat.viewer2.post(f"{ACTIVITY}/{newest['id']}/read")).status_code == 204
    assert (await chat.viewer2.get(count)).json() == {"open": 3, "unread": 2}
    assert (await chat.viewer2.post(f"{ACTIVITY}/{middle['id']}/done")).status_code == 204
    assert (await chat.viewer2.get(count)).json() == {"open": 2, "unread": 1}
    assert [e["id"] for e in await entries(chat.viewer2)] == [newest["id"], oldest["id"]]
    every = await entries(chat.viewer2, include_done=True)
    assert [e["id"] for e in every] == [newest["id"], middle["id"], oldest["id"]]
    assert every[1]["done_at"] is not None and every[1]["read_at"] is not None
    assert (await chat.viewer2.post(f"{ACTIVITY}/read-all")).status_code == 204
    assert (await chat.viewer2.post(f"{ACTIVITY}/read-all")).status_code == 204
    assert (await chat.viewer2.get(count)).json() == {"open": 2, "unread": 0}
    paged = (await chat.viewer2.get(ACTIVITY, params={"limit": 1})).json()
    rest = await entries(chat.viewer2, cursor=paged["next_cursor"])
    assert [e["id"] for e in paged["items"] + rest] == [newest["id"], oldest["id"]]
    assert await _count(session, "activity.changed") == 3  # read, done, read-all


async def test_an_edit_that_adds_a_mention_notifies(chat: Chat, session: AsyncSession) -> None:
    message = await mention(chat, "viewer", "viewer2")
    await deliver(session)
    edited = await chat.viewer.patch(
        f"/api/messages/{message['id']}",
        json={
            "body_md": "auch @editor",
            "mentions": [str(chat.users["viewer2"].id), str(chat.users["editor"].id)],
        },
    )
    assert edited.status_code == 200
    await deliver(session)
    assert [e["reason"] for e in await entries(chat.editor)] == ["mention"]
    assert len(await entries(chat.viewer2)) == 1
    assert (await entries(chat.editor))[0]["snippet"] == "auch @editor"


async def test_deleted_messages_notify_nobody(chat: Chat, session: AsyncSession) -> None:
    kept = await mention(chat, "viewer", "viewer2")
    await deliver(session)
    gone = await mention(chat, "viewer", "viewer2")
    await chat.viewer.delete(f"/api/messages/{gone['id']}")
    await deliver(session)
    assert [e["message_id"] for e in await entries(chat.viewer2)] == [kept["id"]]
    await chat.viewer.delete(f"/api/messages/{kept['id']}")
    assert await entries(chat.viewer2) == []


async def test_the_snippet_is_short(chat: Chat, session: AsyncSession) -> None:
    body = {
        "body_md": "ä" * 300,
        "mentions": [str(chat.users["viewer2"].id)],
    }
    assert (await chat.viewer.post(chat.messages, json=body)).status_code == 201
    await deliver(session)
    (entry,) = await entries(chat.viewer2)
    assert entry["snippet"] == "ä" * 140


async def test_in_a_dm_only_participants_are_notified(
    people: People, session: AsyncSession
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    response = await people.alice.post(
        f"/api/conversations/{dm['id']}/messages",
        json={"body_md": "hey", "mentions": [people.id("bob"), people.id("carol")]},
    )
    assert response.status_code == 201
    await deliver(session)
    (entry,) = await entries(people.bob)
    assert entry["conversation"]["kind"] == "dm" and entry["conversation"]["name"] is None
    assert await entries(people.carol) == []
