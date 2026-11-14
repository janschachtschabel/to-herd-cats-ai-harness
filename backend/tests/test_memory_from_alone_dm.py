"""Memory written from a DM of the person alone with the agent (review M6 finding 16a):
what the model writes there may carry words of the DM itself, which the run's checks
do not see as read, so `update_memory` from such a run writes only into a space that
nobody but the asker reads (no other member, directly or through a group, and not
open); elsewhere it refuses with a tool error the model reads. From a channel or a
thread of the space it writes as before: its words are that place's already."""

import uuid

from app.core.permissions import SpaceRole
from app.modules.agents.toolbox import memory_tools
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.spaces.models import SpaceKind
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
