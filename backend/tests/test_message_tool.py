"""Plan M6 task 6: `post_message` writes an agent message only into the conversation
the run answers in, or into a channel of a space the agent is a member of, with the
run's rights there; never into another DM, and nothing the run read elsewhere into a
space whose audience may not see it."""

import uuid

from sqlalchemy import select

from app.core.principal import PrincipalType
from app.modules.agents.toolbox import message_tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.agents.toolbox.writing import LEAKS
from app.modules.messaging.models import Conversation, ConversationKind, Message, MessageKind
from tests.factories_dms import dm_of
from tests.factories_tools import tool_context
from tests.factories_writing import Work, events


async def _channel(work: Work, space_id: uuid.UUID) -> uuid.UUID:
    found = await work.bench.session.scalar(
        select(Conversation.id).where(
            Conversation.space_id == space_id, Conversation.kind == ConversationKind.CHANNEL
        )
    )
    if found is not None:
        return found
    r = await work.admin.post(f"/api/spaces/{space_id}/channels", json={"name": "allgemein2"})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


async def _agent_messages(work: Work) -> list[Message]:
    stmt = select(Message).where(Message.kind == MessageKind.AGENT).order_by(Message.created_at)
    return list((await work.bench.session.scalars(stmt)).all())


async def test_it_posts_in_its_own_conversation_and_in_a_channel_of_its_space(
    work: Work,
) -> None:
    ctx = await tool_context(work.bench)
    channel = await _channel(work, work.space.id)
    for target in (uuid.UUID(work.bench.dm_id), channel):
        args = message_tools.PostMessageArgs(conversation_id=target, text="Hallo zusammen")
        assert (await message_tools.post_message(ctx, args)).text.startswith("Posted message id=")
    posted = await _agent_messages(work)
    assert [m.conversation_id for m in posted] == [uuid.UUID(work.bench.dm_id), channel]
    for message in posted:
        assert (message.author_type, message.author_id) == ("agent", work.bench.agent.id)
        assert message.run_id == ctx.run.id
    created = await events(work.bench.session, "message.created")
    assert {e.actor_type for e in created if e.subject_id in {m.id for m in posted}} == {
        PrincipalType.AGENT
    }


async def test_it_answers_in_a_thread_of_its_conversation(work: Work) -> None:
    said = await work.bench.say("Frage")
    ctx = await tool_context(work.bench)
    args = message_tools.PostMessageArgs(
        conversation_id=uuid.UUID(work.bench.dm_id), text="Antwort", reply_to=said["id"]
    )
    assert (await message_tools.post_message(ctx, args)).text.startswith("Posted")
    (reply,) = await _agent_messages(work)
    assert str(reply.parent_id) == said["id"]


async def test_no_other_dm_and_no_channel_outside_its_spaces(work: Work) -> None:
    ctx = await tool_context(work.bench)
    other_dm = await dm_of(work.bench.people.alice, work.bench.people.id("bob"))
    outside = await _channel(work, work.private.id)  # Alice reads it, the agent is no member
    for target in (uuid.UUID(other_dm["id"]), outside, uuid.uuid4()):
        args = message_tools.PostMessageArgs(conversation_id=target, text="x")
        assert (await message_tools.post_message(ctx, args)).text == NOT_FOUND
    assert await _agent_messages(work) == []


async def test_what_the_run_read_elsewhere_stays_out_of_a_channel(work: Work) -> None:
    ctx = await tool_context(work.bench)
    ctx.reads.spaces.add(work.private.id)
    channel = await _channel(work, work.space.id)
    args = message_tools.PostMessageArgs(conversation_id=channel, text="Geheimnis")
    assert (await message_tools.post_message(ctx, args)).text == LEAKS
    assert await _agent_messages(work) == []
