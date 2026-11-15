"""Module review M8 4, K1 and K2 (reverting H7 of review 3): under the personal mark
the only place a run writes without the asking person's release is its own DM alone
with her (that message is marked personal). Any other write waits for her release of
exactly that content, wherever it goes: a team space where she is the only member
today (its audience can grow), her personal space, memory pages alike; what is
written there carries no mark, so it may only be what she released."""

import uuid
from dataclasses import replace

import pytest

from app.modules.agents.actor import Reads, run_actor
from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.toolbox import memory_tools, ticket_tools
from app.modules.agents.toolbox.base import CallRef, RunRef, ToolContext
from app.modules.ai.models import DataLocation
from tests.factories_agents import open_agent_dm
from tests.factories_spaces import personal_space_of
from tests.factories_tools import tool_context
from tests.factories_writing import Work, alone_in
from tests.test_personal_agent_reach import pia


async def _marked(work: Work) -> ToolContext:
    ctx = replace(await tool_context(work.bench), call=CallRef(1, "call-1"))  # her DM
    ctx.reads.personal = True
    return ctx


async def test_memory_into_a_space_only_she_reads_waits_for_her(work: Work) -> None:
    await alone_in(work)
    args = memory_tools.UpdateMemoryArgs(space_id=work.space.id, content="merken")
    with pytest.raises(ReleaseFirst):
        await memory_tools.update_memory(await _marked(work), args)


async def test_a_ticket_in_a_team_space_only_she_belongs_to_waits_for_her(work: Work) -> None:
    await alone_in(work)
    args = ticket_tools.CreateTicketArgs(space_id=work.space.id, title="Drucker")
    with pytest.raises(ReleaseFirst):
        await ticket_tools.create_ticket(await _marked(work), args)


async def test_a_ticket_others_read_still_waits_for_her(work: Work) -> None:
    args = ticket_tools.CreateTicketArgs(space_id=work.space.id, title="Drucker")
    with pytest.raises(ReleaseFirst):
        await ticket_tools.create_ticket(await _marked(work), args)


async def test_her_personal_space_waits_for_her_too(work: Work) -> None:
    """A personal agent keeps its memory in her personal space: under the mark that
    waits for her release as well; without the mark it writes at once."""
    bench = work.bench
    alice = bench.people.users["alice"]
    agent = await pia(bench)
    dm = uuid.UUID((await open_agent_dm(bench.people.alice, agent))["id"])
    space = await personal_space_of(bench.session, alice)
    actor = await run_actor(bench.session, alice.org_id, alice.id, agent.id, dm)
    assert actor is not None
    ref = RunRef(uuid.uuid4(), alice.org_id, agent.id, alice.id, dm)
    location = DataLocation(bench.connection.data_location)
    args = memory_tools.UpdateMemoryArgs(space_id=space.id, content="merken")
    for personal in (True, False):
        reads = Reads(personal=personal)
        ctx = ToolContext(bench.session, actor, location, reads, ref, CallRef(1, "call-1"))
        if personal:
            with pytest.raises(ReleaseFirst):
                await memory_tools.update_memory(ctx, args)
        else:
            assert (await memory_tools.update_memory(ctx, args)).text.startswith("Memory saved")
