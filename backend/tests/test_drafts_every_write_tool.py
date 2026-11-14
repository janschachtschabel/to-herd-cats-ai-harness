"""Every tool of the catalog after a draft of the space was read alone with the person
(review M6 2, finding 1): what others than the space's editors may read is refused
(`DRAFTS`), a proposal for a page of the space, `update_page` on a draft there and
the run's own conversation are not. A tool added to the catalog must be named here."""

from collections.abc import Awaitable, Callable

import pytest

from app.core.permissions import SpaceRole
from app.modules.agents.toolbox import (
    memory_tools,
    message_tools,
    reading,
    skill_tools,
    ticket_tools,
    wiki_tools,
)
from app.modules.agents.toolbox.base import Effect, ToolContext
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.agents.toolbox.writing import DRAFTS
from app.modules.spaces.models import AgentWritePolicy
from tests.factories_tools import tool_context
from tests.factories_wiki import new_page
from tests.factories_writing import Work
from tests.test_run_scope_places import channel_in

Call = Callable[[Work, ToolContext], Awaitable[str]]

# Reading tools, and those that write only into the run's own conversation (the place
# that reads the run's answer anyway): no draft check.
UNCHECKED = {
    "search",
    "read_page",
    "read_ticket",
    "list_tree",
    "list_versions",
    "search_tickets",
    "read_conversation",
    "search_past_runs",
    "load_skill",
    "ask_user",  # a question card in the run's own conversation
    "submit_result",  # the final answer, in the run's own conversation
}


async def _key(work: Work) -> str:
    return f"HC-{(await work.ticket())['number']}"


async def _comment(work: Work, ctx: ToolContext) -> str:
    args = ticket_tools.CommentTicketArgs(key=await _key(work), text="t")
    return (await ticket_tools.comment_ticket(ctx, args)).text


async def _status(work: Work, ctx: ToolContext) -> str:
    args = ticket_tools.SetTicketStatusArgs(key=await _key(work), status="In Arbeit")
    return (await ticket_tools.set_ticket_status(ctx, args)).text


async def _create(work: Work, ctx: ToolContext) -> str:
    args = ticket_tools.CreateTicketArgs(space_id=work.space.id, title="t", description_md="d")
    return (await ticket_tools.create_ticket(ctx, args)).text


async def _link(work: Work, ctx: ToolContext) -> str:
    args = ticket_tools.LinkTicketPageArgs(key=await _key(work), page_id=await work.page())
    return (await ticket_tools.link_ticket_page(ctx, args)).text


async def _assign(work: Work, ctx: ToolContext) -> str:
    alice = work.bench.people.users["alice"]
    args = ticket_tools.AssignTicketArgs(
        key=await _key(work), assignee_type="user", assignee_id=alice.id, reason="r"
    )
    return (await ticket_tools.assign_ticket(ctx, args)).text


async def _memory(work: Work, ctx: ToolContext) -> str:
    args = memory_tools.UpdateMemoryArgs(space_id=work.space.id, content="m")
    return (await memory_tools.update_memory(ctx, args)).text


async def _new_page(work: Work, ctx: ToolContext) -> str:
    args = wiki_tools.ProposeNewPageArgs(
        space_id=work.space.id, title="t", content_md="c", reason="r"
    )
    return (await wiki_tools.propose_new_page(ctx, args)).text


async def _skill(work: Work, ctx: ToolContext) -> str:
    args = skill_tools.ProposeSkillArgs(
        kind="new", name="s", space_id=work.space.id, description="d", content="c", reason="r"
    )
    return (await skill_tools.propose_skill(ctx, args)).text


async def _update_published(work: Work, ctx: ToolContext) -> str:
    args = wiki_tools.UpdatePageArgs(page_id=await work.page(), content_md="neu", reason="r")
    return (await wiki_tools.update_page(ctx, args)).text


async def _to_channel(work: Work, ctx: ToolContext) -> str:
    channel = await channel_in(work.bench, work.space)
    args = message_tools.PostMessageArgs(conversation_id=channel.id, text="t")
    return (await message_tools.post_message(ctx, args)).text


async def _change_elsewhere(work: Work, ctx: ToolContext) -> str:
    """A proposal for a page of another space: its editors are not the draft's."""
    made = await new_page(work.admin, work.private.id, "Andere", content_md="a")
    args = wiki_tools.ProposePageChangeArgs(page_id=made["id"], content_md="b", reason="r")
    return (await wiki_tools.propose_page_change(ctx, args)).text


REFUSED: dict[str, Call] = {
    "comment_ticket": _comment,
    "set_ticket_status": _status,
    "create_ticket": _create,
    "link_ticket_page": _link,
    "assign_ticket": _assign,
    "update_memory": _memory,
    "propose_new_page": _new_page,
    "propose_skill": _skill,
    "update_page": _update_published,
    "post_message": _to_channel,
    "propose_page_change": _change_elsewhere,
}


async def _change_here(work: Work, ctx: ToolContext) -> str:
    args = wiki_tools.ProposePageChangeArgs(page_id=await work.page(), content_md="b", reason="r")
    return (await wiki_tools.propose_page_change(ctx, args)).text


async def _update_draft(work: Work, ctx: ToolContext) -> str:
    made = await new_page(work.admin, work.space.id, "Noch ein Entwurf", content_md="a")
    args = wiki_tools.UpdatePageArgs(page_id=made["id"], content_md="b", reason="r")
    return (await wiki_tools.update_page(ctx, args)).text


async def _to_own(work: Work, ctx: ToolContext) -> str:
    args = message_tools.PostMessageArgs(conversation_id=ctx.run.conversation_id, text="t")
    return (await message_tools.post_message(ctx, args)).text


ALLOWED: dict[str, tuple[Call, str]] = {
    "propose_page_change": (_change_here, "Proposal id="),
    "update_page": (_update_draft, "Diff of page"),
    "post_message": (_to_own, "Posted message"),
}


def test_every_tool_of_the_catalog_is_named() -> None:
    assert set(CATALOG) == UNCHECKED | set(REFUSED)
    assert {n for n, spec in CATALOG.items() if spec.effect != Effect.READ} <= set(REFUSED)


async def _after_a_draft(work: Work) -> ToolContext:
    await work.bench.join(work.private, SpaceRole.EDITOR)  # another space it edits
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    await work.bench.session.flush()
    draft = await new_page(work.admin, work.space.id, "Entwurf", content_md="GEHEIM")
    ctx = await tool_context(work.bench)  # alone with Alice
    assert (
        "GEHEIM" in (await reading.read_page(ctx, reading.ReadPageArgs(page_id=draft["id"]))).text
    )
    return ctx


@pytest.mark.parametrize("name", sorted(REFUSED))
async def test_a_write_others_read_is_refused(work: Work, name: str) -> None:
    ctx = await _after_a_draft(work)
    assert await REFUSED[name](work, ctx) == DRAFTS


@pytest.mark.parametrize("name", sorted(ALLOWED))
async def test_what_only_the_editors_read_is_allowed(work: Work, name: str) -> None:
    ctx = await _after_a_draft(work)
    tool, done = ALLOWED[name]
    said = await tool(work, ctx)
    assert said.startswith(done), said
