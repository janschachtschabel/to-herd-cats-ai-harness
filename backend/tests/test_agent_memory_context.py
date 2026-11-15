"""Plan M6 task 9, decision 10 (spec 8.3 point 2, 8.5): a run's context holds the
memory pages of the spaces its actor reads (its read scope included) whose AI policy
lets its connection receive them, the place's space first, then by space name;
together at most 4,000 characters, shared out equally, what a page leaves unused
going to the ones after it, a cut marked. Each page is framed as untrusted data, and
reading it counts: its space is one the run has read."""

import re

import pytest
from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.modules.agents import memory
from app.modules.agents.memory_models import AgentMemory
from app.modules.agents.run_models import StopReason
from app.modules.ai.models import AiPolicy, DataLocation
from app.modules.spaces.models import SpaceKind
from tests.factories_spaces import MakeSpace
from tests.factories_tools import call, tool_context
from tests.factories_writing import Work, alone_in
from tests.test_agent_memory import remember
from tests.test_run_scope_places import actor_in, channel_in


@pytest.fixture
async def work(work: Work) -> Work:
    """`work`, with Alice the only person who reads its space, so memory from her DM
    alone with the agent may go there (`alone_in`)."""
    await alone_in(work)
    return work


def _prompts(work: Work) -> list[str]:
    return [r.text for r in work.bench.stub.state.log if r.path.endswith("/chat/completions")]


def test_the_budget_is_shared_and_what_is_left_goes_on() -> None:
    budget = memory.MEMORY_BUDGET
    halves = memory.fit(["a" * 3_000, "b" * 3_000], budget)
    assert [len(t) for t in halves] == [budget // 2, budget // 2]
    assert all(t.endswith(memory.CUT_MARK) for t in halves)
    short_first = memory.fit(["a" * 500, "b" * 5_000], budget)
    assert short_first[0] == "a" * 500 and len(short_first[1]) == budget - 500
    assert memory.fit(["a" * 10, "b" * 20], budget) == ["a" * 10, "b" * 20]
    many = memory.fit(["c" * 1_000] * 600, budget)
    assert sum(map(len, many)) <= budget and many[-1] == ""  # no room left: left out
    assert len(many[0]) == memory.MIN_SHARE  # the first ones are shown


async def test_a_run_reads_its_memory_framed_as_data(work: Work) -> None:
    await remember(await tool_context(work.bench), work.space.id, "Merke: Inventur-77.")
    await work.bench.say("Hallo")
    assert await work.bench.run_next() == StopReason.COMPLETED
    (prompt,) = _prompts(work)
    assert "Inventur-77" in prompt
    assert '<untrusted source=\\"memory\\"' in prompt
    assert f'space_id=\\"{work.space.id}\\"' in prompt


async def test_without_memory_the_context_says_nothing_about_it(work: Work) -> None:
    await work.bench.say("Hallo")
    await work.bench.run_next()
    (prompt,) = _prompts(work)
    assert 'source=\\"memory\\"' not in prompt


async def test_memory_counts_as_read(work: Work, make_space: MakeSpace) -> None:
    """Read from Werkstatt (a team space), it may not go into another team space."""
    alice = work.bench.people.users["alice"]
    other = await make_space(SpaceKind.TEAM, "Anderswo", members=[(alice, SpaceRole.EDITOR)])
    await work.bench.join(other, SpaceRole.EDITOR)
    await remember(await tool_context(work.bench), work.space.id, "Merke: Inventur-77.")
    work.bench.agent.level = 2
    await work.bench.session.flush()
    args = {"space_id": str(other.id), "title": "Aus dem Gedächtnis"}
    work.bench.stub.state.replies.extend([call("create_ticket", **args), {"content": "Done."}])
    await work.bench.say("Lege ein Ticket an")
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert "may not be shown to the people of that space" in work.bench.stub.state.texts()


async def test_only_spaces_whose_policy_lets_the_connection_receive_them(work: Work) -> None:
    await remember(await tool_context(work.bench), work.space.id, "Merke: Inventur-77.")
    work.space.ai_policy = AiPolicy.RESTRICTED
    work.space.allowed_locations = ["eu"]
    await work.bench.session.flush()
    actor = await actor_in(work.bench, work.bench.dm_id)
    agent = work.bench.agent.id
    found = await memory.for_run(work.bench.session, actor, agent, DataLocation.EXTERNAL, None)
    assert found.text is None and found.spaces == frozenset()
    found = await memory.for_run(work.bench.session, actor, agent, DataLocation.EU, None)
    assert found.text is not None and "Inventur-77" in found.text
    assert found.spaces == frozenset({work.space.id})


async def test_the_place_first_then_by_name_within_the_budget(
    work: Work, make_space: MakeSpace
) -> None:
    alice = work.bench.people.users["alice"]
    spaces = {
        name: await make_space(kind, name, members=[(alice, SpaceRole.EDITOR)])
        for name, kind in (("Alpha", SpaceKind.OPEN), ("Beta", SpaceKind.OPEN))
    }
    channels = {}
    for name, space in spaces.items():
        await work.bench.join(space, SpaceRole.EDITOR)
        channels[name] = await channel_in(work.bench, space)  # open: not from a DM alone
        ctx = await tool_context(work.bench, channels[name].id)
        await remember(ctx, space.id, f"{name}-" + "m" * 3_000)
    session, agent = work.bench.session, work.bench.agent.id
    alone = await actor_in(work.bench, work.bench.dm_id)
    found = await memory.for_run(session, alone, agent, DataLocation.LOCAL, None)
    assert found.text is not None
    assert found.text.index("Alpha-") < found.text.index("Beta-")
    assert sum(len(m) for m in re.findall("m{20,}", found.text)) <= memory.MEMORY_BUDGET
    in_beta = await actor_in(work.bench, channels["Beta"].id)
    found = await memory.for_run(session, in_beta, agent, DataLocation.LOCAL, spaces["Beta"].id)
    assert found.text is not None
    assert found.text.index("Beta-") < found.text.index("Alpha-")
    pages = await session.scalars(select(AgentMemory.page_id))
    assert found.pages == frozenset(pages.all())
