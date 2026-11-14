"""No writing tool writes into a space closed to AI (`ai_policy = none`; spec 7.3,
review M6 finding 5): every tool that names a space answers "not found", as for a
space it cannot see, through the one check `toolbox/writing.closed_to_ai`. Tools that
name a page or a ticket find none there in the first place (their reads filter such
spaces out)."""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select

from app.modules.agents.toolbox import (
    memory_tools,
    message_tools,
    skill_tools,
    ticket_tools,
    wiki_tools,
)
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.ai.models import AiPolicy
from app.modules.messaging.models import Message, MessageKind
from app.runtime.loop import ToolResult
from tests.factories_tools import tool_context
from tests.factories_writing import Work, alone_in, set_level

Write = Callable[[ToolContext, uuid.UUID, uuid.UUID], Awaitable[ToolResult]]


async def _post(ctx: ToolContext, space: uuid.UUID, channel: uuid.UUID) -> ToolResult:
    args = message_tools.PostMessageArgs(conversation_id=channel, text="Hallo")
    return await message_tools.post_message(ctx, args)


async def _memory(ctx: ToolContext, space: uuid.UUID, channel: uuid.UUID) -> ToolResult:
    args = memory_tools.UpdateMemoryArgs(space_id=space, content="Notiz")
    return await memory_tools.update_memory(ctx, args)


async def _ticket(ctx: ToolContext, space: uuid.UUID, channel: uuid.UUID) -> ToolResult:
    args = ticket_tools.CreateTicketArgs(space_id=space, title="Neu")
    return await ticket_tools.create_ticket(ctx, args)


async def _page(ctx: ToolContext, space: uuid.UUID, channel: uuid.UUID) -> ToolResult:
    args = wiki_tools.ProposeNewPageArgs(space_id=space, title="Neu", content_md="x", reason="r")
    return await wiki_tools.propose_new_page(ctx, args)


async def _skill(ctx: ToolContext, space: uuid.UUID, channel: uuid.UUID) -> ToolResult:
    args = skill_tools.ProposeSkillArgs(
        kind="new", name="neu", space_id=space, description="d", content="c", reason="r"
    )
    return await skill_tools.propose_skill(ctx, args)


WRITES: dict[str, Write] = {
    "post_message": _post,
    "update_memory": _memory,
    "create_ticket": _ticket,
    "propose_new_page": _page,
    "propose_skill": _skill,
}


@pytest.mark.parametrize("tool", sorted(WRITES))
async def test_no_tool_writes_into_a_space_closed_to_ai(work: Work, tool: str) -> None:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    assert r.status_code == 201, r.text
    channel = uuid.UUID(r.json()["id"])
    await set_level(work.bench, 3)
    work.space.ai_policy = AiPolicy.NONE
    await work.bench.session.flush()
    ctx = await tool_context(work.bench)
    assert (await WRITES[tool](ctx, work.space.id, channel)).text == NOT_FOUND
    posted = select(Message.id).where(Message.kind == MessageKind.AGENT)
    assert await work.bench.session.scalar(posted) is None


@pytest.mark.parametrize("tool", ["post_message", "update_memory"])
async def test_the_same_tools_write_once_the_space_is_open_to_ai(work: Work, tool: str) -> None:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    channel = uuid.UUID(r.json()["id"])
    await set_level(work.bench, 3)
    await alone_in(work)  # memory from Alice's DM alone: only where she alone reads
    ctx = await tool_context(work.bench)
    text = (await WRITES[tool](ctx, work.space.id, channel)).text
    assert text.startswith(("Posted message", "Memory saved")), text
