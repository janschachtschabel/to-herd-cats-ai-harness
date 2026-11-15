"""Plan M6 task 6: the wiki's writing tools. `propose_page_change` and
`propose_new_page` make proposals written for the agent (its run named); `update_page`
writes in two steps, only where the space lets agents write directly: a version holds
the content before the write, the write is a version of source `agent` by the agent
with the run, and a new generation ends live sessions. Never into a page locked for
AI or of a space whose policy is `none`; nothing the run read elsewhere goes into a
space whose audience may not see it."""

import re
import uuid

import pytest
from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.agents.toolbox import wiki_tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.agents.toolbox.writing import LEAKS
from app.modules.ai.models import AiPolicy
from app.modules.proposals.models import PageProposal
from app.modules.spaces.models import AgentWritePolicy, SpaceMember
from app.modules.wiki.models import Page, PageVersion, VersionSource
from tests.factories_tools import tool_context
from tests.factories_writing import Work, events

NEW = "eins\nZWEI\ndrei\n"


async def _page(work: Work, page_id: str) -> Page:
    page = await work.bench.session.scalar(
        select(Page).where(Page.id == uuid.UUID(page_id)).execution_options(populate_existing=True)
    )
    assert page is not None
    return page


async def _versions(work: Work, page_id: str) -> list[PageVersion]:
    stmt = (
        select(PageVersion)
        .where(PageVersion.page_id == uuid.UUID(page_id))
        .order_by(PageVersion.number)
        .execution_options(populate_existing=True)
    )
    return list((await work.bench.session.scalars(stmt)).all())


async def _direct(work: Work) -> None:
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    await work.bench.session.flush()


# --- proposals -----------------------------------------------------------------------


async def test_a_change_is_proposed_for_the_agent_naming_the_run(work: Work) -> None:
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    args = wiki_tools.ProposePageChangeArgs(page_id=page_id, content_md=NEW, reason="Tippfehler")
    result = await wiki_tools.propose_page_change(ctx, args)
    assert result.text.startswith("Proposal id=")
    proposal = await work.bench.session.scalar(select(PageProposal))
    assert proposal is not None
    assert (proposal.author_type, proposal.author_id) == ("agent", work.bench.agent.id)
    assert (proposal.run_id, proposal.content_md) == (ctx.run.id, NEW)
    (event,) = await events(work.bench.session, "proposal.created")
    assert (event.actor_type, event.actor_id) == (PrincipalType.AGENT, work.bench.agent.id)
    assert (await _page(work, page_id)).content_md == "eins\nzwei\n"  # nothing written


async def test_a_new_page_is_proposed_at_the_top_or_under_a_parent(work: Work) -> None:
    parent = await work.page("Handbuch")
    ctx = await tool_context(work.bench)
    for parent_id in (None, uuid.UUID(parent)):
        args = wiki_tools.ProposeNewPageArgs(
            space_id=work.space.id, parent_id=parent_id, title="Neu", content_md="x", reason="r"
        )
        assert (await wiki_tools.propose_new_page(ctx, args)).text.startswith("Proposal id=")
    rows = (await work.bench.session.scalars(select(PageProposal))).all()
    assert sorted(str(p.parent_id) for p in rows) == sorted(["None", parent])
    assert {p.author_id for p in rows} == {work.bench.agent.id}


async def test_proposing_needs_the_right_to_edit_for_the_run(work: Work) -> None:
    page_id = await work.page()
    member = await work.bench.session.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == work.space.id, SpaceMember.member_id == work.bench.agent.id
        )
    )
    assert member is not None
    member.role = SpaceRole.VIEWER  # the agent only views: Alice's rights are held to it
    await work.bench.session.flush()
    ctx = await tool_context(work.bench)
    change = wiki_tools.ProposePageChangeArgs(page_id=page_id, content_md=NEW, reason="r")
    assert (await wiki_tools.propose_page_change(ctx, change)).text == "Not allowed here."
    new = wiki_tools.ProposeNewPageArgs(
        space_id=work.space.id, title="N", content_md="x", reason="r"
    )
    assert (await wiki_tools.propose_new_page(ctx, new)).text == NOT_FOUND
    assert await work.bench.session.scalar(select(PageProposal)) is None


@pytest.mark.parametrize("lock", ["no_ai", "policy_none", "private", "unknown"])
async def test_what_ai_may_not_read_cannot_be_proposed_for(work: Work, lock: str) -> None:
    page_id = await work.page()
    page = await _page(work, page_id)
    if lock == "no_ai":
        page.no_ai = True
    elif lock == "policy_none":
        work.space.ai_policy = AiPolicy.NONE
    elif lock == "private":
        page.space_id = work.private.id
    await work.bench.session.flush()
    ctx = await tool_context(work.bench)
    target = uuid.uuid4() if lock == "unknown" else uuid.UUID(page_id)
    args = wiki_tools.ProposePageChangeArgs(page_id=target, content_md=NEW, reason="r")
    assert (await wiki_tools.propose_page_change(ctx, args)).text == NOT_FOUND
    assert await work.bench.session.scalar(select(PageProposal)) is None


async def test_nothing_read_elsewhere_goes_into_a_space_that_may_not_see_it(work: Work) -> None:
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    ctx.reads.spaces.add(work.private.id)  # the run read the private space before
    args = wiki_tools.ProposePageChangeArgs(page_id=page_id, content_md=NEW, reason="r")
    assert (await wiki_tools.propose_page_change(ctx, args)).text == LEAKS
    ctx.reads.spaces.clear()
    assert (await wiki_tools.propose_page_change(ctx, args)).text.startswith("Proposal id=")


# --- update_page -----------------------------------------------------------------------


async def test_update_page_shows_the_diff_then_writes_with_its_token(work: Work) -> None:
    await _direct(work)
    page_id = await work.page()
    before = await _page(work, page_id)
    generation, version = before.collab_generation, before.version
    ctx = await tool_context(work.bench)
    args = wiki_tools.UpdatePageArgs(page_id=page_id, content_md=NEW, reason="Klarer")
    preview = await wiki_tools.update_page(ctx, args)
    assert "- zwei" in preview.text and "+ ZWEI" in preview.text and "+ drei" in preview.text
    assert preview.spaces == frozenset({work.space.id})
    assert (await _page(work, page_id)).content_md == "eins\nzwei\n"  # nothing written yet
    token = re.search(r'token="([0-9a-f]+)"', preview.text)
    assert token is not None
    written = await wiki_tools.update_page(ctx, args.model_copy(update={"token": token[1]}))
    assert written.text.startswith(f"Page id={page_id} saved")
    after = await _page(work, page_id)
    assert after.content_md == NEW
    assert (after.collab_generation, after.version) == (generation + 1, version + 1)
    assert (after.updated_by_type, after.updated_by_id) == ("agent", work.bench.agent.id)
    *_, previous, last = await _versions(work, page_id)
    assert previous.content_md == "eins\nzwei\n"  # the content before the agent's write
    assert (last.source, last.author_type, last.author_id) == (
        VersionSource.AGENT,
        "agent",
        work.bench.agent.id,
    )
    assert (last.run_id, last.change_summary, last.content_md) == (ctx.run.id, "Klarer", NEW)


async def test_a_token_from_before_a_change_writes_nothing(work: Work) -> None:
    await _direct(work)
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    args = wiki_tools.UpdatePageArgs(page_id=page_id, content_md=NEW, reason="r")
    token = re.search(r'token="([0-9a-f]+)"', (await wiki_tools.update_page(ctx, args)).text)
    assert token is not None
    page = await _page(work, page_id)
    page.content_md, page.version = "eins\nzwei\nvon Hand\n", page.version + 1
    await work.bench.session.flush()
    again = await wiki_tools.update_page(ctx, args.model_copy(update={"token": token[1]}))
    assert "+ ZWEI" in again.text and "token=" in again.text  # a fresh diff and token
    assert (await _page(work, page_id)).content_md == "eins\nzwei\nvon Hand\n"
    other = args.model_copy(update={"token": token[1], "content_md": "anders\n"})
    assert "saved" not in (await wiki_tools.update_page(ctx, other)).text  # bound to content


async def test_update_page_tells_to_propose_where_the_space_takes_proposals(work: Work) -> None:
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    args = wiki_tools.UpdatePageArgs(page_id=page_id, content_md=NEW, reason="r")
    assert (await wiki_tools.update_page(ctx, args)).text == wiki_tools.PROPOSE_INSTEAD


async def test_update_page_never_writes_a_page_locked_for_ai(work: Work) -> None:
    await _direct(work)
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    args = wiki_tools.UpdatePageArgs(page_id=page_id, content_md=NEW, reason="r")
    token = re.search(r'token="([0-9a-f]+)"', (await wiki_tools.update_page(ctx, args)).text)
    assert token is not None
    page = await _page(work, page_id)
    page.no_ai = True  # locked between preview and write
    await work.bench.session.flush()
    result = await wiki_tools.update_page(ctx, args.model_copy(update={"token": token[1]}))
    assert result.text == NOT_FOUND
    assert (await _page(work, page_id)).content_md == "eins\nzwei\n"
