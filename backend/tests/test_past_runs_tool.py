"""Plan M6 task 4: `search_past_runs` finds earlier runs of this agent for the person
who asks now, and only what the current run may read: a tool result while every space
it came from is readable now (the redaction rule of the run view), the model's own
words while every space their run read is; outside a DM alone with the agent, only
runs of the same conversation (another place's audience is not this one's)."""

import uuid

import pytest
from sqlalchemy import select

from app.core.models_base import utcnow
from app.core.permissions import SpaceRole
from app.modules.agents.past_runs_repository import PastRunRepository
from app.modules.agents.run_models import Run, StopReason
from app.modules.agents.toolbox import past_runs
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.ai.models import AiPolicy
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from app.modules.wiki.models import Page
from tests.factories_agents import Bench, make_agent, open_agent_dm
from tests.factories_spaces import MakeSpace
from tests.factories_tools import call, tool_context
from tests.factories_wiki import new_page, publish
from tests.test_run_scope_places import dm_of

WORD = "Okapi77"


@pytest.fixture
async def space(bench: Bench, make_space: MakeSpace) -> Space:
    alice, bob = bench.people.users["alice"], bench.people.users["bob"]
    made = await make_space(
        SpaceKind.TEAM, members=[(alice, SpaceRole.EDITOR), (bob, SpaceRole.EDITOR)]
    )
    await bench.join(made, SpaceRole.EDITOR)
    await bench.locate("local")
    return made


async def past_run(bench: Bench, space: Space, dm: str | None = None, who: str = "alice") -> None:
    """A finished run that read a page of `space` and answered with its word."""
    admin = bench.people.admin
    page = await publish(admin, await new_page(admin, space.id, "Zoo", content_md=WORD))
    bench.stub.state.replies.extend(
        [call("read_page", page_id=page["id"]), {"content": f"The word is {WORD}."}]
    )
    await bench.say("What is the word?", who=who, dm=dm)
    assert await bench.run_next() == StopReason.COMPLETED


async def found(bench: Bench, conversation: object | None = None, who: str = "alice") -> str:
    ctx = await tool_context(bench, conversation, who=who)
    result = await past_runs.search_past_runs(ctx, past_runs.SearchPastRunsArgs(query=WORD))
    return result.text


async def test_it_finds_the_askers_earlier_runs(bench: Bench, space: Space) -> None:
    await past_run(bench, space)
    ctx = await tool_context(bench)
    result = await past_runs.search_past_runs(ctx, past_runs.SearchPastRunsArgs(query=WORD))
    assert result.text.count(WORD) >= 2  # the page read and the answer
    run_id = await bench.session.scalar(select(Run.id))
    assert f"run {run_id}" in result.text
    assert result.spaces == frozenset({space.id}) and ctx.reads.spaces == {space.id}
    assert ctx.reads.pages  # the pages its hits read count for this run's checks


async def test_another_askers_runs_are_not_found(bench: Bench, space: Space) -> None:
    await past_run(bench, space)
    bob_dm = await open_agent_dm(bench.people.bob, bench.agent)
    assert await found(bench, bob_dm["id"], who="bob") == NOT_FOUND


async def test_another_agents_runs_are_not_found(bench: Bench, space: Space) -> None:
    await past_run(bench, space)
    other = await make_agent(bench.session, bench.people, bench.connection.id, name="Other")
    for run in await bench.session.scalars(select(Run)):
        run.agent_id = other.id
    await bench.session.flush()
    assert await found(bench) == NOT_FOUND


async def test_the_current_run_is_not_its_own_past(bench: Bench, space: Space) -> None:
    await past_run(bench, space)
    run_id = await bench.session.scalar(select(Run.id))
    assert run_id is not None
    ctx = await tool_context(bench, run_id=run_id)
    result = await past_runs.search_past_runs(ctx, past_runs.SearchPastRunsArgs(query=WORD))
    assert result.text == NOT_FOUND


@pytest.mark.parametrize("lost", ["agent_left", "alice_left", "restricted", "none"])
async def test_nothing_from_a_space_the_run_may_not_read_now(
    bench: Bench, space: Space, lost: str
) -> None:
    """Neither the page read then nor the answer that quoted it."""
    await past_run(bench, space)
    if lost in ("agent_left", "alice_left"):
        member = bench.agent.id if lost == "agent_left" else bench.people.users["alice"].id
        row = await bench.session.scalar(
            select(SpaceMember).where(
                SpaceMember.space_id == space.id, SpaceMember.member_id == member
            )
        )
        assert row is not None
        await bench.session.delete(row)
    elif lost == "restricted":
        space.ai_policy, space.allowed_locations = AiPolicy.RESTRICTED, ["eu"]
    else:
        space.ai_policy = AiPolicy.NONE
    await bench.session.flush()
    assert await found(bench) == NOT_FOUND


async def test_a_run_that_read_nothing_is_found_alone_with_the_agent(bench: Bench) -> None:
    bench.stub.state.replies.append({"content": f"Remember {WORD}."})
    await bench.say("Hello")
    assert await bench.run_next() == StopReason.COMPLETED
    assert WORD in await found(bench)


async def test_with_others_only_runs_of_the_same_conversation(bench: Bench, space: Space) -> None:
    """A run in Alice's DM alone is not found in her DM with Bob; one there is."""
    await past_run(bench, space)
    with_bob = await dm_of(bench, "alice", "bob")
    assert await found(bench, with_bob.id) == NOT_FOUND
    await past_run(bench, space, dm=str(with_bob.id))
    shown = await found(bench, with_bob.id)
    there = await bench.session.scalar(select(Run.id).where(Run.conversation_id == with_bob.id))
    assert f"run {there}" in shown
    alone = await bench.session.scalar(
        select(Run.id).where(Run.conversation_id == uuid.UUID(bench.dm_id))
    )
    assert f"run {alone}" not in shown


async def test_with_others_nothing_one_of_them_may_not_read_now(bench: Bench, space: Space) -> None:
    """Same conversation, but Bob has left the space its run read since."""
    with_bob = await dm_of(bench, "alice", "bob")
    await past_run(bench, space, dm=str(with_bob.id))
    assert WORD in await found(bench, with_bob.id)
    row = await bench.session.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == space.id,
            SpaceMember.member_id == bench.people.users["bob"].id,
        )
    )
    assert row is not None
    await bench.session.delete(row)
    await bench.session.flush()
    assert await found(bench, with_bob.id) == NOT_FOUND


async def test_a_query_is_text_not_a_pattern(bench: Bench, space: Space) -> None:
    await past_run(bench, space)
    for query in ("%", "_", "\\"):
        ctx = await tool_context(bench)
        args = past_runs.SearchPastRunsArgs(query=query)
        assert (await past_runs.search_past_runs(ctx, args)).text == NOT_FOUND


async def test_search_past_runs_in_a_run(bench: Bench, space: Space) -> None:
    await past_run(bench, space)
    bench.stub.state.replies.extend([call("search_past_runs", query=WORD), {"content": "Ok."}])
    await bench.say("What did you find before?")
    assert await bench.run_next() == StopReason.COMPLETED
    assert '<untrusted source=\\"past_runs\\"' in bench.stub.state.texts()


async def test_in_a_shared_dm_another_askers_runs_are_not_found(bench: Bench, space: Space) -> None:
    """Bob sees the conversation, but the run there answered Alice."""
    with_bob = await dm_of(bench, "alice", "bob")
    await past_run(bench, space, dm=str(with_bob.id))
    assert WORD in await found(bench, with_bob.id)
    assert await found(bench, with_bob.id, who="bob") == NOT_FOUND


@pytest.mark.parametrize("since", ["trashed", "locked", "moved_restricted", "moved_away"])
async def test_a_page_changed_since_counts_where_it_is_now(
    bench: Bench, space: Space, make_space: MakeSpace, since: str
) -> None:
    await past_run(bench, space)
    page = await bench.session.scalar(select(Page).where(Page.title == "Zoo"))
    assert page is not None
    if since == "trashed":
        page.trashed_at = utcnow()
    elif since == "locked":
        page.no_ai = True
    else:
        alice = bench.people.users["alice"]
        members = [(alice, SpaceRole.EDITOR)] if since == "moved_restricted" else []
        elsewhere = await make_space(SpaceKind.TEAM, members=members)
        await bench.join(elsewhere, SpaceRole.EDITOR)
        if since == "moved_restricted":
            elsewhere.ai_policy, elsewhere.allowed_locations = AiPolicy.RESTRICTED, ["eu"]
        page.space_id = elsewhere.id
    await bench.session.flush()
    assert await found(bench) == NOT_FOUND


async def test_the_statement_keeps_to_the_readable_spaces(bench: Bench, space: Space) -> None:
    """The repository alone: what it is given as readable decides, in SQL."""
    await past_run(bench, space)
    repo = PastRunRepository(bench.session, bench.agent.org_id)

    async def kinds(readable: object) -> set[str]:
        hits = await repo.search(
            agent_id=bench.agent.id,
            user_id=bench.people.users["alice"].id,
            exclude=uuid.uuid4(),
            text=WORD,
            readable=readable,  # type: ignore[arg-type]
            conversation_id=None,
            limit=10,
        )
        return {h.kind for h in hits}

    everywhere = select(Space.id).where(Space.id == space.id)
    nowhere = select(Space.id).where(Space.id != space.id)
    assert await kinds(everywhere) == {"tool_call", "model_call"}
    assert await kinds(nowhere) == set()
