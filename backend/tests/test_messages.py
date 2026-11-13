"""Messages and one-level threads in channels (spec 6.1, 6.2).

Whoever sees a channel reads it; writing needs `channel.post` (from `viewer`); only
the author edits; the author or someone with `channel.manage` deletes (softly: the
text goes, replies stay). A message in a conversation the caller cannot see answers
404 `message.not_found`.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.audit.models import AuditLog
from app.modules.messaging.models import Conversation, Message, MessageKind
from app.modules.spaces.models import Space, SpaceKind
from tests.conftest import json_lines
from tests.factories_messaging import Chat, post, send


def _message(message_id: object) -> str:
    return f"/api/messages/{message_id}"


async def test_viewers_post_and_everyone_who_sees_reads(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "Hallo **alle**")
    assert message["kind"] == "human" and message["body_md"] == "Hallo **alle**"
    assert message["author"] == {"type": "user", "id": str(chat.users["viewer"].id)}
    assert message["conversation_id"] == chat.channel_id and message["parent_id"] is None
    assert (message["reply_count"], message["last_reply_at"]) == (0, None)
    assert (message["edited_at"], message["deleted_at"]) == (None, None)
    for reader in (chat.viewer2, chat.editor, chat.moderator, chat.admin):
        listed = (await reader.get(chat.messages)).json()["items"]
        assert [m["id"] for m in listed] == [message["id"]]


async def test_guests_post_only_where_they_are_members(
    owner: AsyncClient, guest_client: AsyncClient, guest, open_space: Space, make_space
) -> None:
    public = (await owner.post(f"/api/spaces/{open_space.id}/channels", json={"name": "o"})).json()
    hidden = await send(guest_client, public["id"], "Hallo")
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "conversation.not_found"
    space = await make_space(SpaceKind.TEAM, members=[(guest, "viewer")])
    mine = (await owner.post(f"/api/spaces/{space.id}/channels", json={"name": "g"})).json()
    assert (await send(guest_client, mine["id"], "Hallo")).status_code == 201


async def test_outsiders_neither_read_nor_write(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "intern")
    for response in (
        await chat.outsider.get(chat.messages),
        await send(chat.outsider, chat.channel_id, "rein"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation.not_found"
    for method, path, body in (
        ("GET", f"{_message(message['id'])}/replies", None),
        ("PATCH", _message(message["id"]), {"body_md": "x"}),
        ("DELETE", _message(message["id"]), None),
    ):
        response = await chat.outsider.request(method, path, json=body)
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "message.not_found"
    reply = await send(chat.outsider, chat.channel_id, "x", parent_id=message["id"])
    assert reply.status_code == 404


async def test_only_the_author_edits(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "Tippfeler")
    edited = await chat.viewer.patch(_message(message["id"]), json={"body_md": "Tippfehler"})
    assert edited.status_code == 200
    assert edited.json()["body_md"] == "Tippfehler" and edited.json()["edited_at"] is not None
    for other in (chat.viewer2, chat.moderator, chat.admin):
        refused = await other.patch(_message(message["id"]), json={"body_md": "fremd"})
        assert refused.status_code == 403
        assert refused.json()["error"]["code"] == "message.not_author"
    listed = (await chat.viewer2.get(chat.messages)).json()["items"]
    assert listed[0]["body_md"] == "Tippfehler"


async def test_authors_and_moderators_delete_and_the_text_goes(
    chat: Chat, session: AsyncSession
) -> None:
    own = await post(chat.viewer, chat.channel_id, "meins")
    assert (await chat.viewer.delete(_message(own["id"]))).status_code == 204
    other = await post(chat.viewer, chat.channel_id, "von viewer")
    refused = await chat.viewer2.delete(_message(other["id"]))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "message.not_author"
    assert (await chat.editor.delete(_message(other["id"]))).status_code == 403
    assert (await chat.moderator.delete(_message(other["id"]))).status_code == 204
    assert (await chat.moderator.delete(_message(other["id"]))).status_code == 204  # again
    listed = (await chat.viewer2.get(chat.messages)).json()["items"]
    assert all(m["deleted_at"] is not None and m["body_md"] == "" for m in listed)
    stored = await session.get(Message, uuid.UUID(other["id"]))
    assert stored is not None and stored.body_md == ""
    edit = await chat.viewer.patch(_message(other["id"]), json={"body_md": "zurück"})
    assert edit.status_code == 409 and edit.json()["error"]["code"] == "message.deleted"
    audited = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "message.moderated"))
    ).all()
    assert [(a.target_id, a.actor_id) for a in audited] == [
        (uuid.UUID(other["id"]), chat.users["moderator"].id)
    ]


async def test_replies_stay_when_the_parent_is_deleted(chat: Chat) -> None:
    parent = await post(chat.viewer, chat.channel_id, "Frage")
    reply = await post(chat.viewer2, chat.channel_id, "Antwort", parent_id=parent["id"])
    assert reply["parent_id"] == parent["id"]
    assert (await chat.viewer.delete(_message(parent["id"]))).status_code == 204
    replies = (await chat.viewer.get(f"{_message(parent['id'])}/replies")).json()["items"]
    assert [r["body_md"] for r in replies] == ["Antwort"]
    top = (await chat.viewer.get(chat.messages)).json()["items"]
    assert [(m["id"], m["reply_count"], m["body_md"]) for m in top] == [(parent["id"], 1, "")]
    late = await send(chat.viewer2, chat.channel_id, "Nachzügler", parent_id=parent["id"])
    assert late.status_code == 201


async def test_threads_have_one_level(chat: Chat, make_space, owner: AsyncClient) -> None:
    parent = await post(chat.viewer, chat.channel_id, "Frage")
    reply = await post(chat.viewer2, chat.channel_id, "Antwort", parent_id=parent["id"])
    nested = await send(chat.viewer, chat.channel_id, "tiefer", parent_id=reply["id"])
    assert nested.status_code == 422 and nested.json()["error"]["code"] == "message.bad_parent"
    other = (
        await chat.moderator.post(f"/api/spaces/{chat.space.id}/channels", json={"name": "anderer"})
    ).json()
    elsewhere = await send(chat.viewer, other["id"], "falsch", parent_id=parent["id"])
    assert elsewhere.status_code == 422
    unknown = await send(chat.viewer, chat.channel_id, "?", parent_id=uuid.uuid4())
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "message.bad_parent"
    top = (await chat.viewer.get(chat.messages)).json()["items"]
    assert [(m["id"], m["reply_count"]) for m in top] == [(parent["id"], 1)]
    assert top[0]["last_reply_at"] == reply["created_at"]


async def test_resending_with_the_same_client_id_returns_the_first_message(
    chat: Chat, session: AsyncSession
) -> None:
    client_id = uuid.uuid4()
    first = await send(chat.viewer, chat.channel_id, "einmal", client_id=client_id)
    again = await send(chat.viewer, chat.channel_id, "einmal", client_id=client_id)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert first.json()["client_id"] == str(client_id)
    assert len((await chat.viewer.get(chat.messages)).json()["items"]) == 1
    events = await session.scalars(select(EventOutbox).where(EventOutbox.type == "message.created"))
    assert len(events.all()) == 1
    other = await send(chat.viewer2, chat.channel_id, "auch", client_id=client_id)
    assert other.status_code == 201  # another author's key
    parent = first.json()["id"]
    misused = await send(chat.viewer, chat.channel_id, "x", client_id=client_id, parent_id=parent)
    assert misused.status_code == 409
    assert misused.json()["error"]["code"] == "message.client_id_conflict"


async def test_archived_channels_take_no_writes(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "vorher")
    archived = await chat.moderator.post(
        f"/api/conversations/{chat.channel_id}/archive", json={"version": 1}
    )
    assert archived.status_code == 200
    for response in (
        await send(chat.viewer, chat.channel_id, "nachher"),
        await send(chat.viewer, chat.channel_id, "antwort", parent_id=message["id"]),
        await chat.viewer.patch(_message(message["id"]), json={"body_md": "neu"}),
        await chat.viewer.delete(_message(message["id"])),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conversation.archived"
    assert len((await chat.viewer.get(chat.messages)).json()["items"]) == 1


async def test_bodies_are_validated(chat: Chat) -> None:
    assert (await send(chat.viewer, chat.channel_id, "x" * 20_000)).status_code == 201
    for bad in ({"body_md": "x" * 20_001}, {"body_md": ""}, {"body_md": " \n\t"}, {}):
        response = await chat.viewer.post(chat.messages, json=bad)
        assert response.status_code == 422, bad
    smuggled = await chat.viewer.post(chat.messages, json={"body_md": "x", "kind": "system"})
    assert smuggled.status_code == 422
    message = await post(chat.viewer, chat.channel_id, "ok")
    too_long = await chat.viewer.patch(_message(message["id"]), json={"body_md": "x" * 20_001})
    assert too_long.status_code == 422


async def test_lists_are_paginated_newest_first_with_threads_apart(chat: Chat) -> None:
    sent = [await post(chat.viewer, chat.channel_id, f"m{i}") for i in range(5)]
    await post(chat.viewer2, chat.channel_id, "antwort", parent_id=sent[0]["id"])
    first = (await chat.viewer.get(chat.messages, params={"limit": 2})).json()
    assert [m["body_md"] for m in first["items"]] == ["m4", "m3"]
    rest = (
        await chat.viewer.get(chat.messages, params={"limit": 10, "cursor": first["next_cursor"]})
    ).json()
    assert [m["body_md"] for m in rest["items"]] == ["m2", "m1", "m0"]
    assert rest["next_cursor"] is None
    before = await chat.viewer.get(chat.messages, params={"before": sent[2]["id"]})
    assert [m["body_md"] for m in before.json()["items"]] == ["m1", "m0"]
    after = await chat.viewer.get(chat.messages, params={"after": sent[1]["id"], "limit": 2})
    assert [m["body_md"] for m in after.json()["items"]] == ["m2", "m3"]  # oldest first
    more = await chat.viewer.get(
        chat.messages, params={"after": sent[1]["id"], "cursor": after.json()["next_cursor"]}
    )
    assert [m["body_md"] for m in more.json()["items"]] == ["m4"]
    both = await chat.viewer.get(
        chat.messages, params={"after": sent[1]["id"], "before": sent[3]["id"]}
    )
    assert both.status_code == 422


async def test_replies_are_oldest_first_and_paginated(chat: Chat) -> None:
    parent = await post(chat.viewer, chat.channel_id, "Frage")
    for i in range(3):
        await post(chat.viewer2, chat.channel_id, f"a{i}", parent_id=parent["id"])
    path = f"{_message(parent['id'])}/replies"
    first = (await chat.viewer.get(path, params={"limit": 2})).json()
    rest = (await chat.viewer.get(path, params={"cursor": first["next_cursor"]})).json()
    assert [m["body_md"] for m in first["items"] + rest["items"]] == ["a0", "a1", "a2"]
    reply_id = first["items"][0]["id"]
    assert (await chat.viewer.get(f"{_message(reply_id)}/replies")).json()["items"] == []


async def test_events_carry_ids_and_never_text(chat: Chat, session: AsyncSession) -> None:
    parent = await post(chat.viewer, chat.channel_id, "Geheimnis-1")
    reply = await post(chat.viewer2, chat.channel_id, "Geheimnis-2", parent_id=parent["id"])
    await chat.viewer.patch(_message(parent["id"]), json={"body_md": "Geheimnis-3"})
    await chat.viewer.delete(_message(parent["id"]))
    events = (
        await session.scalars(
            select(EventOutbox)
            .where(EventOutbox.subject_type == "message")
            .order_by(EventOutbox.id)
        )
    ).all()
    assert [(e.type, e.subject_id) for e in events] == [
        ("message.created", uuid.UUID(parent["id"])),
        ("message.created", uuid.UUID(reply["id"])),
        ("message.updated", uuid.UUID(parent["id"])),
        ("message.deleted", uuid.UUID(parent["id"])),
    ]
    assert events[1].payload == {
        "conversation_id": chat.channel_id,
        "message_id": reply["id"],
        "parent_id": parent["id"],
    }
    assert events[0].payload["parent_id"] is None
    assert {e.space_id for e in events} == {chat.space.id}
    assert "Geheimnis" not in str([e.payload for e in events])


async def test_message_text_is_never_logged(chat: Chat, capsys: pytest.CaptureFixture[str]) -> None:
    message = await post(chat.viewer, chat.channel_id, "Streng-vertraulich-8812")
    await chat.viewer.patch(_message(message["id"]), json={"body_md": "Streng-vertraulich-8813"})
    out = capsys.readouterr().out
    assert json_lines(out) and "Streng-vertraulich" not in out


async def _channel(session: AsyncSession, chat: Chat) -> Conversation:
    channel = await session.get(Conversation, uuid.UUID(chat.channel_id))
    assert channel is not None
    return channel


async def test_the_database_refuses_system_messages_in_channels(
    chat: Chat, session: AsyncSession
) -> None:
    """Review focus 7: not even a direct write past the services puts a system message
    into a channel, nor turns a message into one, nor a channel into another kind."""
    channel = await _channel(session, chat)
    with pytest.raises(DBAPIError) as refused:
        async with session.begin_nested():
            session.add(
                Message(
                    org_id=channel.org_id,
                    conversation_id=channel.id,
                    author_type="system",
                    author_id=None,
                    kind=MessageKind.SYSTEM,
                    body_md='{"key": "page.published"}',
                )
            )
            await session.flush()
    assert "system_message_outside_thread" in str(refused.value.orig)
    human = await post(chat.viewer, chat.channel_id, "normal")
    for statement, reason in (
        (
            "UPDATE message SET kind = 'system', author_type = 'system', author_id = NULL"
            " WHERE id = :id",
            "system_message_outside_thread",
        ),
        ("UPDATE conversation SET kind = 'dm' WHERE id = :conversation", "conversation_kind_fixed"),
    ):
        with pytest.raises(DBAPIError) as refused:
            async with session.begin_nested():
                await session.execute(
                    text(statement), {"id": human["id"], "conversation": chat.channel_id}
                )
        assert reason in str(refused.value.orig)
