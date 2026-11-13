"""One-level threads held by the database (review M3 N15): not even a write past the
services makes a reply to a reply, a reply whose parent is in another conversation,
or a reply out of a message that has replies itself."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import Conversation, Message, MessageKind
from tests.factories_messaging import Chat, post


async def _refused(session: AsyncSession, statement: str, **params: object) -> str:
    with pytest.raises(DBAPIError) as refused:
        async with session.begin_nested():
            await session.execute(text(statement), params)
    return str(refused.value.orig)


async def _insert_reply(session: AsyncSession, conversation: Conversation, parent: str) -> None:
    session.add(
        Message(
            org_id=conversation.org_id,
            conversation_id=conversation.id,
            parent_id=uuid.UUID(parent),
            author_type="user",
            author_id=uuid.uuid4(),
            kind=MessageKind.HUMAN,
            body_md="direkt",
        )
    )
    await session.flush()


async def test_the_database_keeps_threads_one_level_deep(chat: Chat, session: AsyncSession) -> None:
    channel = await session.get(Conversation, uuid.UUID(chat.channel_id))
    assert channel is not None
    top = await post(chat.viewer, chat.channel_id, "oben")
    reply = await post(chat.viewer, chat.channel_id, "Antwort", parent_id=top["id"])
    other_channel = (
        await chat.moderator.post(f"/api/spaces/{chat.space.id}/channels", json={"name": "b"})
    ).json()
    elsewhere = await post(chat.viewer, other_channel["id"], "drüben")

    for parent in (reply["id"], elsewhere["id"]):  # a reply's reply; another conversation
        with pytest.raises(DBAPIError) as refused:
            async with session.begin_nested():
                await _insert_reply(session, channel, parent)
        assert "reply_not_one_level" in str(refused.value.orig)

    reason = await _refused(  # a message with replies cannot become a reply
        session,
        "UPDATE message SET parent_id = :parent WHERE id = :id",
        parent=uuid.UUID(elsewhere["id"]),
        id=uuid.UUID(top["id"]),
    )
    assert "reply_not_one_level" in reason
    reason = await _refused(  # nor move away from its replies
        session,
        "UPDATE message SET conversation_id = :other WHERE id = :id",
        other=uuid.UUID(other_channel["id"]),
        id=uuid.UUID(top["id"]),
    )
    assert "reply_not_one_level" in reason

    async with session.begin_nested():  # a reply to a top-level message is fine
        await _insert_reply(session, channel, top["id"])
