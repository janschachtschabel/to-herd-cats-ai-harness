"""Module review M8 3, H3: under the personal mark a tool asks the person's release
only once nothing else refuses the call. The draft mark, a leak, a space closed to AI
and every other refusal of the tool come first; the release is asked right before the
write itself (`writing.effect`), so she is never asked to release what is refused
anyway."""

from dataclasses import replace

import pytest

from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.toolbox import memory_tools, message_tools, ticket_tools
from app.modules.agents.toolbox.base import NOT_FOUND, CallRef, ToolContext
from app.modules.agents.toolbox.writing import DRAFTS, LEAKS
from app.modules.ai.models import AiPolicy
from tests.factories_tools import tool_context
from tests.factories_writing import Work
from tests.test_run_scope_places import channel_in


async def _marked(work: Work, conversation: object | None = None) -> ToolContext:
    ctx = replace(await tool_context(work.bench, conversation), call=CallRef(1, "call-1"))
    ctx.reads.personal = True
    return ctx


async def _post(ctx: ToolContext, conversation: object) -> str:
    args = message_tools.PostMessageArgs(conversation_id=conversation, text="t")
    try:
        result = await message_tools.post_message(ctx, args)
    except ReleaseFirst:
        raise AssertionError("a release is asked for a call that is refused") from None
    return result.text


async def test_a_draft_refuses_before_a_release_is_asked(work: Work) -> None:
    channel = await channel_in(work.bench, work.space)
    ctx = await _marked(work, channel.id)
    ctx.reads.drafts.add(work.private.id)  # a draft of another space was read
    assert await _post(ctx, channel.id) == DRAFTS


async def test_a_leak_refuses_before_a_release_is_asked(work: Work) -> None:
    channel = await channel_in(work.bench, work.space)
    ctx = await _marked(work, channel.id)
    ctx.reads.spaces.add(work.private.id)  # read where the channel's people may not
    assert await _post(ctx, channel.id) == LEAKS


async def test_a_space_closed_to_ai_refuses_before_a_release_is_asked(work: Work) -> None:
    channel = await channel_in(work.bench, work.space)
    work.space.ai_policy = AiPolicy.NONE
    await work.bench.session.flush()
    assert await _post(await _marked(work, channel.id), channel.id) == NOT_FOUND


async def test_the_tools_own_refusal_comes_before_a_release(work: Work) -> None:
    """`create_ticket` with a parent it cannot find: refused, nobody asked."""
    ctx = await _marked(work)
    args = ticket_tools.CreateTicketArgs(
        space_id=work.space.id, title="Drucker", parent_key="HC-999"
    )
    result = await ticket_tools.create_ticket(ctx, args)
    assert result.failed and result.text == NOT_FOUND


async def test_memory_from_her_dm_into_a_shared_space_is_refused_unasked(work: Work) -> None:
    ctx = await _marked(work)  # her DM alone with the agent
    args = memory_tools.UpdateMemoryArgs(space_id=work.space.id, content="merken")
    result = await memory_tools.update_memory(ctx, args)
    assert result.text == memory_tools.SHARED_SPACE


async def test_a_call_nothing_refuses_asks_for_the_release(work: Work) -> None:
    channel = await channel_in(work.bench, work.space)
    with pytest.raises(ReleaseFirst):
        await message_tools.post_message(
            await _marked(work, channel.id),
            message_tools.PostMessageArgs(conversation_id=channel.id, text="t"),
        )
