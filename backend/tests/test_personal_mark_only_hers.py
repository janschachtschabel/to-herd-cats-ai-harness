"""Module review M8 3, H7: under the personal mark, a write that nobody but the
asking person can read needs no release: memory into her own space from her DM, a
ticket in a space only she reads. Anything others read still waits for her."""

from dataclasses import replace

import pytest

from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.toolbox import memory_tools, ticket_tools
from app.modules.agents.toolbox.base import CallRef, ToolContext
from tests.factories_tools import tool_context
from tests.factories_writing import Work, alone_in


async def _marked(work: Work) -> ToolContext:
    ctx = replace(await tool_context(work.bench), call=CallRef(1, "call-1"))  # her DM
    ctx.reads.personal = True
    return ctx


async def test_memory_into_a_space_only_she_reads_needs_no_release(work: Work) -> None:
    await alone_in(work)
    args = memory_tools.UpdateMemoryArgs(space_id=work.space.id, content="merken")
    result = await memory_tools.update_memory(await _marked(work), args)
    assert result.text.startswith("Memory saved"), result.text


async def test_a_ticket_only_she_reads_needs_no_release(work: Work) -> None:
    await alone_in(work)
    args = ticket_tools.CreateTicketArgs(space_id=work.space.id, title="Drucker")
    result = await ticket_tools.create_ticket(await _marked(work), args)
    assert result.text.startswith("Created HC-"), result.text


async def test_a_ticket_others_read_still_waits_for_her(work: Work) -> None:
    args = ticket_tools.CreateTicketArgs(space_id=work.space.id, title="Drucker")
    with pytest.raises(ReleaseFirst):
        await ticket_tools.create_ticket(await _marked(work), args)
