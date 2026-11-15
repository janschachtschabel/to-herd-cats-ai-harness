"""Plan M6 task 4: `read_conversation` reads only the conversation the run answers in
(its arguments name no conversation), as the person who asked sees it, with the
replies of one of its messages on request; in a space's conversation it names that
space as its source. `submit_result` ends the run with its text as the answer, once,
also when the run is taken up again after it was recorded."""

import json
import uuid
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.models_base import utcnow
from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.agents.run_models import Run, StopReason
from app.modules.agents.step_host import RunHost
from app.modules.agents.toolbox import conversation as tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.messaging.models import MAX_BODY_CHARS, Message, MessageKind
from app.modules.spaces.models import SpaceKind
from tests.factories_agents import Bench, open_agent_dm
from tests.factories_spaces import MakeSpace
from tests.factories_tools import call, tool_context
from tests.test_run_scope_places import channel_in, dm_of


async def reply_to(bench: Bench, message_id: str, text: str) -> None:
    r = await bench.people.alice.post(
        f"/api/conversations/{bench.dm_id}/messages",
        json={"body_md": text, "parent_id": message_id},
    )
    assert r.status_code == 201, r.text


async def test_it_reads_the_runs_conversation_oldest_first_with_authors(bench: Bench) -> None:
    await bench.say("First words")
    await bench.say("Second words")
    ctx = await tool_context(bench)
    result = await tools.read_conversation(ctx, tools.ReadConversationArgs())
    text = result.text
    assert text.index("First words") < text.index("Second words")
    assert "Alice" in text
    assert result.spaces == frozenset()  # a DM: the person's own content, from no space


async def test_older_messages_and_replies_on_request(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tools, "MESSAGES", 2)
    first = await bench.say("Oldest")
    await bench.say("Middle")
    last = await bench.say("Newest")
    await reply_to(bench, first["id"], "A reply below")
    ctx = await tool_context(bench)
    newest = await tools.read_conversation(ctx, tools.ReadConversationArgs())
    assert "Oldest" not in newest.text and "Newest" in newest.text
    assert "A reply below" not in newest.text
    older = await tools.read_conversation(
        ctx, tools.ReadConversationArgs(before=uuid.UUID(last["id"]))
    )
    assert "Oldest" in older.text and "Newest" not in older.text
    replies = await tools.read_conversation(
        ctx, tools.ReadConversationArgs(replies_to=uuid.UUID(first["id"]))
    )
    assert "A reply below" in replies.text and "Middle" not in replies.text


async def test_no_other_conversation_can_be_read(bench: Bench) -> None:
    """Bob's DM with the agent: neither by an argument nor through one of its ids."""
    other = await open_agent_dm(bench.people.bob, bench.agent)
    r = await bench.people.bob.post(
        f"/api/conversations/{other['id']}/messages", json={"body_md": "Bob's secret"}
    )
    assert r.status_code == 201
    with pytest.raises(ValidationError):
        tools.ReadConversationArgs.model_validate({"conversation_id": other["id"]})
    ctx = await tool_context(bench)
    for args in (
        tools.ReadConversationArgs(replies_to=uuid.UUID(r.json()["id"])),
        tools.ReadConversationArgs(before=uuid.UUID(r.json()["id"])),
    ):
        result = await tools.read_conversation(ctx, args)
        assert "Bob's secret" not in result.text
    replies = await tools.read_conversation(
        ctx, tools.ReadConversationArgs(replies_to=uuid.UUID(r.json()["id"]))
    )
    assert replies.text == NOT_FOUND


async def test_replies_of_another_conversation_she_sees_are_not_read(bench: Bench) -> None:
    """Alice takes part in a DM with Bob and the agent too: still not this one."""
    elsewhere = await dm_of(bench, "alice", "bob")
    posted = await bench.say("Over there", dm=str(elsewhere.id))
    await bench.people.alice.post(
        f"/api/conversations/{elsewhere.id}/messages",
        json={"body_md": "Reply over there", "parent_id": posted["id"]},
    )
    ctx = await tool_context(bench)
    args = tools.ReadConversationArgs(replies_to=uuid.UUID(posted["id"]))
    result = await tools.read_conversation(ctx, args)
    assert result.text == NOT_FOUND


async def test_in_a_channel_the_space_is_the_source(bench: Bench, make_space: MakeSpace) -> None:
    alice = bench.people.users["alice"]
    space = await make_space(SpaceKind.TEAM, members=[(alice, SpaceRole.EDITOR)])
    await bench.join(space, SpaceRole.EDITOR)
    channel = await channel_in(bench, space)
    bench.session.add(
        Message(
            org_id=space.org_id,
            conversation_id=channel.id,
            author_type=PrincipalType.USER,
            author_id=alice.id,
            kind=MessageKind.HUMAN,
            body_md="In the channel",
        )
    )
    await bench.session.flush()
    ctx = await tool_context(bench, channel.id)
    result = await tools.read_conversation(ctx, tools.ReadConversationArgs())
    assert "In the channel" in result.text
    assert result.spaces == frozenset({space.id}) and ctx.reads.spaces == {space.id}


async def test_submit_result_ends_the_run_with_its_text(bench: Bench) -> None:
    bench.stub.state.replies.extend(
        [call("submit_result", text="The result."), {"content": "never asked"}]
    )
    await bench.say("Work")
    assert await bench.run_next() == StopReason.COMPLETED
    assert len(bench.stub.state.log) == 1  # no model call after the result
    answers = [m["body_md"] for m in await bench.messages() if m["kind"] == "agent"]
    assert answers == ["The result."]


async def test_a_result_recorded_before_a_crash_is_answered_once(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Crash(BaseException):
        pass

    original = RunHost.call_tool

    async def dying(self: RunHost, *args: object) -> object:
        await original(self, *args)  # type: ignore[arg-type]
        raise Crash

    monkeypatch.setattr(RunHost, "call_tool", dying)
    bench.stub.state.replies.extend([call("submit_result", text="Once."), {"content": "no"}])
    await bench.say("Work")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    for run in await bench.session.scalars(select(Run)):
        run.lease_until = utcnow() - timedelta(seconds=1)
    await bench.session.flush()
    assert await bench.run_next() == StopReason.COMPLETED
    assert len(bench.stub.state.log) == 1  # replayed: no provider call
    answers = [m["body_md"] for m in await bench.messages() if m["kind"] == "agent"]
    assert answers == ["Once."]


def test_a_result_must_be_a_message() -> None:
    with pytest.raises(ValidationError):
        tools.SubmitResultArgs(text="   ")
    with pytest.raises(ValidationError):
        tools.SubmitResultArgs(text="x" * (MAX_BODY_CHARS + 1))
    assert tools.SubmitResultArgs(text="ok").text == "ok"


async def test_read_conversation_in_a_run(bench: Bench) -> None:
    await bench.say("Earlier remark")
    bench.stub.state.replies.extend([call("read_conversation"), {"content": "Read."}])
    await bench.say("What did I say?")
    assert await bench.run_next() == StopReason.COMPLETED
    second = json.dumps(bench.stub.state.log[1].body["messages"])
    assert '<untrusted source=\\"conversation\\"' in second
