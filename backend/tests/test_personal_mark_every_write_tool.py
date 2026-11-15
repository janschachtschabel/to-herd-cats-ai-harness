"""The personal mark and every writing tool (follow-up to plan M8 task 7; module
review M8 2, finding G2): a run that holds what the asking person read through her
own connector (`Reads.personal`) writes nothing others may read without her release.
Every such tool stops before its effect (`ReleaseFirst`, which the host turns into a
release of the call); released, it goes on and writes, the draft's exceptions (a
proposal or `update_page` in the draft's space) included. Into its own conversation
alone with the person no release is needed; where others read along, a message there
asks for the release too, and a question stays refused (`PERSONAL`)."""

from dataclasses import replace

import pytest

from app.core.permissions import SpaceRole
from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.toolbox import message_tools, questions
from app.modules.agents.toolbox.base import CallRef, ToolContext, Wait
from app.modules.agents.toolbox.writing import DRAFTS, LEAKS, PERSONAL
from app.modules.spaces.models import AgentWritePolicy
from tests.factories_tools import tool_context
from tests.factories_writing import Work
from tests.test_drafts_every_write_tool import ALLOWED, REFUSED, Call
from tests.test_run_scope_places import channel_in

# What a draft leaves open (a proposal or a draft's update in its space): not this.
EVERY: dict[str, Call] = {
    **REFUSED,
    **{f"{name} (draft's space)": tool for name, (tool, _) in ALLOWED.items()},
}
del EVERY["post_message (draft's space)"]  # the own conversation: below


async def _marked(work: Work, conversation_id: object | None = None) -> ToolContext:
    await work.bench.join(work.private, SpaceRole.EDITOR)  # another space it edits
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    await work.bench.session.flush()
    ctx = await tool_context(work.bench, conversation_id)  # default: alone with Alice
    ctx.reads.personal = True
    return replace(ctx, call=CallRef(1, "call-1"))


@pytest.mark.parametrize("name", sorted(EVERY))
async def test_a_write_others_read_waits_for_her_release(work: Work, name: str) -> None:
    ctx = await _marked(work)
    with pytest.raises(ReleaseFirst):
        await EVERY[name](work, ctx)


@pytest.mark.parametrize("name", sorted(EVERY))
async def test_once_released_it_writes(work: Work, name: str) -> None:
    ctx = replace(await _marked(work), released=True)
    text = await EVERY[name](work, ctx)
    assert text not in (PERSONAL, DRAFTS, LEAKS) and not text.startswith("Not allowed"), text


async def test_alone_with_the_person_the_run_still_answers(work: Work) -> None:
    ctx = await _marked(work)
    args = message_tools.PostMessageArgs(conversation_id=ctx.run.conversation_id, text="t")
    assert (await message_tools.post_message(ctx, args)).text.startswith("Posted message")


async def test_in_a_channel_its_own_conversation_asks_and_its_question_is_refused(
    work: Work,
) -> None:
    channel = await channel_in(work.bench, work.space)
    ctx = await _marked(work, channel.id)
    args = message_tools.PostMessageArgs(conversation_id=channel.id, text="t")
    with pytest.raises(ReleaseFirst):
        await message_tools.post_message(ctx, args)
    released = await message_tools.post_message(replace(ctx, released=True), args)
    assert released.text.startswith("Posted message")
    asked = await questions.ask_user(ctx, questions.AskUserArgs(question="Welches?"))
    assert not isinstance(asked, Wait) and asked.text == PERSONAL


async def test_without_the_mark_the_channel_is_open(work: Work) -> None:
    channel = await channel_in(work.bench, work.space)
    ctx = await _marked(work, channel.id)
    ctx.reads.personal = False
    args = message_tools.PostMessageArgs(conversation_id=channel.id, text="t")
    assert (await message_tools.post_message(ctx, args)).text.startswith("Posted message")
