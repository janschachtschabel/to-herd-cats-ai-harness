"""Memory written from a DM of the person alone with the agent (review M6 finding 16a):
what the model writes there may carry words of the DM itself, which the run's checks
do not see as read, so `update_memory` from such a run writes only into a space that
nobody but the asker reads (no other member, directly or through a group, and not
open); elsewhere it refuses with a tool error the model reads. From a channel or a
thread of the space it writes as before: its words are that place's already."""

import uuid

from app.core.permissions import SpaceRole
from app.modules.agents.memory_repository import MemoryRepository
from app.modules.agents.toolbox import memory_tools, wiki_tools
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.spaces.models import AgentWritePolicy, SpaceKind
from tests.factories_spaces import MakeSpace
from tests.factories_tools import tool_context
from tests.factories_writing import Work
from tests.test_run_scope_places import channel_in


async def _remember(work: Work, space_id: uuid.UUID, where: object | None = None) -> str:
    ctx = await tool_context(work.bench, where)
    args = memory_tools.UpdateMemoryArgs(space_id=space_id, content="Notiz aus dem Gespräch")
    return (await memory_tools.update_memory(ctx, args)).text


async def test_from_a_dm_alone_only_into_a_space_nobody_else_reads(
    work: Work, make_space: MakeSpace
) -> None:
    alice = work.bench.people.users["alice"]
    own = await make_space(SpaceKind.TEAM, name="Nur Alice", members=[(alice, SpaceRole.EDITOR)])
    await work.bench.join(own, SpaceRole.EDITOR)
    assert (await _remember(work, own.id)).startswith("Memory saved")
    refused = await _remember(work, work.space.id)  # the admin reads it too
    assert refused.startswith("Refused (memory.shared_space)"), refused
    assert "nobody but the person" in refused


async def test_from_a_dm_alone_not_into_an_open_space(work: Work, make_space: MakeSpace) -> None:
    alice = work.bench.people.users["alice"]
    hall = await make_space(SpaceKind.OPEN, name="Halle", members=[(alice, SpaceRole.EDITOR)])
    await work.bench.join(hall, SpaceRole.EDITOR)
    assert (await _remember(work, hall.id)).startswith("Refused (memory.shared_space)")


async def test_from_a_place_of_the_space_it_writes_there(work: Work) -> None:
    channel = await channel_in(work.bench, work.space)
    assert (await _remember(work, work.space.id, channel.id)).startswith("Memory saved")


def test_the_tools_help_says_so() -> None:
    assert "only into a space nobody else reads" in CATALOG["update_memory"].description


async def test_update_page_leaves_memory_pages_to_update_memory(work: Work) -> None:
    """A memory page is an ordinary wiki page; `update_page` refuses it from any place,
    so the rule above is the only way in (review M6 2, finding 3)."""
    bench = work.bench
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    await bench.session.flush()
    channel = await channel_in(bench, work.space)
    there = await tool_context(bench, channel.id)
    first = memory_tools.UpdateMemoryArgs(space_id=work.space.id, content="Notiz")
    assert (await memory_tools.update_memory(there, first)).text.startswith("Memory saved")
    memory = await MemoryRepository(bench.session, bench.agent.org_id).get(
        bench.agent.id, work.space.id
    )
    assert memory is not None
    words = "Was Alice nur in der DM sagte"
    alone = await tool_context(bench)
    refused = memory_tools.UpdateMemoryArgs(space_id=work.space.id, content=words)
    assert (await memory_tools.update_memory(alone, refused)).text.startswith("Refused (memory.")
    for ctx in (alone, await tool_context(bench, channel.id)):
        change = wiki_tools.UpdatePageArgs(page_id=memory.page_id, content_md=words, reason="r")
        said = (await wiki_tools.update_page(ctx, change)).text
        assert said == wiki_tools.USE_UPDATE_MEMORY, said
