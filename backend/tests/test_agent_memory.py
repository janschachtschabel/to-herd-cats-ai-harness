"""Plan M6 task 9, decision 10 (spec 8.5): an agent's memory is one ordinary wiki page
per agent and space at `_agenten/<agent>/gedaechtnis`, made by its first
`update_memory(space, content)` (level 2, allowed directly whatever the space's
`agent_write_policy`), with versions (source `agent`, the agent as author, the run)
and generations; people correct it like any page. Only in spaces of the run's write
scope where the agent may edit pages, never on a page locked for AI, at most 8,000
characters."""

import uuid
from typing import Any

from sqlalchemy import func, select

from app.core.permissions import SpaceRole
from app.modules.agents.memory_models import AgentMemory
from app.modules.agents.toolbox import memory_tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.agents.toolbox.writing import LEAKS
from app.modules.spaces.models import AgentWritePolicy, SpaceKind
from app.modules.wiki.models import Page, PageStatus, PageVersion
from tests.factories_spaces import MakeSpace
from tests.factories_tools import tool_context
from tests.factories_writing import Work
from tests.test_run_scope_places import channel_in

PATH = "_agenten/ava/gedaechtnis"


async def remember(ctx: Any, space_id: object, content: str) -> str:
    args = memory_tools.UpdateMemoryArgs(space_id=uuid.UUID(str(space_id)), content=content)
    return (await memory_tools.update_memory(ctx, args)).text


async def page_at(work: Work, path: str, space_id: object | None = None) -> Page | None:
    stmt = select(Page).where(
        Page.path == path,
        Page.space_id == uuid.UUID(str(space_id or work.space.id)),
        Page.trashed_at.is_(None),
    )
    return await work.bench.session.scalar(stmt.execution_options(populate_existing=True))


async def memory_page(work: Work, space_id: object | None = None) -> Page:
    page = await page_at(work, PATH, space_id)
    assert page is not None
    return page


def test_update_memory_is_a_writing_tool_of_level_2() -> None:
    spec = CATALOG["update_memory"]
    assert (spec.level, spec.effect.value) == (2, "write")


async def test_the_first_update_makes_the_page_and_later_ones_version_it(work: Work) -> None:
    assert work.space.agent_write_policy == AgentWritePolicy.PROPOSE  # allowed directly
    ctx = await tool_context(work.bench)
    text = await remember(ctx, work.space.id, "Merke: Montags Inventur.")
    page = await memory_page(work)
    assert f"page id={page.id}" in text
    assert page.content_md == "Merke: Montags Inventur."
    assert page.status == PageStatus.PUBLISHED and page.title == "Gedächtnis"
    folder = await page_at(work, "_agenten/ava")
    top = await page_at(work, "_agenten")
    assert folder is not None and top is not None
    assert (folder.title, folder.parent_id, page.parent_id) == ("Ava", top.id, folder.id)
    assert (page.created_by_type, page.created_by_id) == ("agent", work.bench.agent.id)
    (mapping,) = (await work.bench.session.scalars(select(AgentMemory))).all()
    assert (mapping.agent_id, mapping.space_id, mapping.page_id) == (
        work.bench.agent.id,
        work.space.id,
        page.id,
    )
    generation = page.collab_generation
    work.bench.agent.name = "Ava Neu"  # renamed: the mapping keeps the page
    await work.bench.session.flush()
    later = await tool_context(work.bench)
    await remember(later, work.space.id, "Merke: Dienstags Inventur.")
    page = await memory_page(work)
    assert page.content_md == "Merke: Dienstags Inventur."
    assert page.collab_generation == generation + 1  # live sessions end
    versions = (
        await work.bench.session.scalars(
            select(PageVersion).where(PageVersion.page_id == page.id).order_by(PageVersion.number)
        )
    ).all()
    assert [(v.source, v.author_type, v.run_id) for v in versions] == [
        ("agent", "agent", ctx.run.id),
        ("agent", "agent", later.run.id),
    ]
    assert await work.bench.session.scalar(select(func.count()).select_from(AgentMemory)) == 1


async def test_people_correct_the_memory_like_any_page(work: Work) -> None:
    await remember(await tool_context(work.bench), work.space.id, "Falsch.")
    page = await memory_page(work)
    r = await work.admin.patch(
        f"/api/pages/{page.id}", json={"version": page.version, "content_md": "Richtig."}
    )
    assert r.status_code == 200, r.text
    await remember(await tool_context(work.bench), work.space.id, "Richtig. Und mehr.")
    assert (await memory_page(work)).id == page.id


async def test_memory_holds_at_most_8000_characters(work: Work) -> None:
    ctx = await tool_context(work.bench)
    text = await remember(ctx, work.space.id, "x" * (memory_tools.MAX_MEMORY_CHARS + 1))
    assert "memory.too_long" in text and "8,000" in text and "Shorten" in text
    assert await page_at(work, PATH) is None
    assert await page_at(work, "_agenten") is None
    await remember(ctx, work.space.id, "x" * memory_tools.MAX_MEMORY_CHARS)
    assert len((await memory_page(work)).content_md) == memory_tools.MAX_MEMORY_CHARS


async def test_never_on_a_page_locked_for_ai(work: Work) -> None:
    await remember(await tool_context(work.bench), work.space.id, "Erstens.")
    page = await memory_page(work)
    r = await work.admin.put(
        f"/api/pages/{page.id}/ai-lock", json={"no_ai": True, "version": page.version}
    )
    assert r.status_code == 200, r.text
    text = await remember(await tool_context(work.bench), work.space.id, "Zweitens.")
    assert "memory.locked" in text
    page = await memory_page(work)
    assert page.content_md == "Erstens." and page.no_ai
    assert await work.bench.session.scalar(select(func.count()).select_from(Page)) == 3


async def test_only_where_the_run_may_edit_pages(work: Work, make_space: MakeSpace) -> None:
    ctx = await tool_context(work.bench)
    assert await remember(ctx, work.private.id, "x") == NOT_FOUND  # the agent is no member
    viewing = await make_space(
        SpaceKind.TEAM, "Lesesaal", members=[(work.bench.people.users["alice"], SpaceRole.EDITOR)]
    )
    await work.bench.join(viewing, SpaceRole.VIEWER)
    ctx = await tool_context(work.bench)  # the actor as of now
    assert await remember(ctx, viewing.id, "x") == "Not allowed here."
    open_space = await make_space(
        SpaceKind.OPEN, "Offen", members=[(work.bench.people.users["alice"], SpaceRole.EDITOR)]
    )
    await work.bench.join(open_space, SpaceRole.EDITOR)
    channel = await channel_in(work.bench, work.space)  # writes in Werkstatt only
    in_channel = await tool_context(work.bench, channel.id)
    assert await remember(in_channel, open_space.id, "x") == "Not allowed here."
    assert "saved" in await remember(in_channel, work.space.id, "Aus dem Kanal.")
    assert await remember(ctx, uuid.uuid4(), "x") == NOT_FOUND


async def test_nothing_read_elsewhere_goes_into_memory(work: Work, make_space: MakeSpace) -> None:
    other = await make_space(
        SpaceKind.TEAM, "Anderswo", members=[(work.bench.people.users["alice"], SpaceRole.EDITOR)]
    )
    await work.bench.join(other, SpaceRole.EDITOR)
    ctx = await tool_context(work.bench)
    ctx.reads.spaces.add(other.id)
    assert await remember(ctx, work.space.id, "Geheimnis von anderswo") == LEAKS
    assert await page_at(work, PATH) is None


async def test_a_trashed_memory_is_made_anew(work: Work) -> None:
    await remember(await tool_context(work.bench), work.space.id, "Alt.")
    old = await memory_page(work)
    top = await page_at(work, "_agenten")
    assert top is not None
    r = await work.admin.post(f"/api/pages/{top.id}/trash", json={"version": top.version})
    assert r.status_code == 204, r.text
    await remember(await tool_context(work.bench), work.space.id, "Neu.")
    new = await memory_page(work)
    assert new.id != old.id and new.content_md == "Neu."
    mapping = await work.bench.session.scalar(
        select(AgentMemory).execution_options(populate_existing=True)
    )
    assert mapping is not None and mapping.page_id == new.id


async def test_a_moved_memory_stays_the_agents(work: Work) -> None:
    await remember(await tool_context(work.bench), work.space.id, "Hier.")
    page = await memory_page(work)
    r = await work.admin.post(
        f"/api/pages/{page.id}/move", json={"parent_id": None, "version": page.version}
    )
    assert r.status_code == 200, r.text
    await remember(await tool_context(work.bench), work.space.id, "Immer noch hier.")
    moved = await page_at(work, "gedaechtnis")
    assert moved is not None and moved.id == page.id
    assert moved.content_md == "Immer noch hier."


async def test_a_page_no_longer_in_its_space_is_not_written(
    work: Work, make_space: MakeSpace
) -> None:
    """No path moves a page between spaces; were there one, the page would be the
    other space's (here one the run may write too), and the memory of this one is
    made anew."""
    alice = work.bench.people.users["alice"]
    other = await make_space(SpaceKind.TEAM, "Anderswo", members=[(alice, SpaceRole.EDITOR)])
    await work.bench.join(other, SpaceRole.EDITOR)
    await remember(await tool_context(work.bench), work.space.id, "Hier.")
    page = await memory_page(work)
    page.space_id = other.id
    await work.bench.session.flush()
    await remember(await tool_context(work.bench), work.space.id, "Neu.")
    gone = await work.bench.session.get(Page, page.id, populate_existing=True)
    assert gone is not None and gone.content_md == "Hier."
    assert (await memory_page(work)).content_md == "Neu."
