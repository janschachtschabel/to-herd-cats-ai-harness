"""`update_memory` (plan M6 decision 10, spec 8.5): level 2, writes directly.

The run's memory page in a space (`agents/memory.py`), its whole content replaced.
Allowed directly at level 2, whatever the space's `agent_write_policy` (memory is
the agent's own page, not a page of the space it would propose changes to), but only
where the run may edit pages (`page.edit` for the run's actor: the person's rights ∩
the agent's role ∩ the place's write scope), only what that space's audience may
receive (`writing.leaks_into`), never on a page locked for AI, and at most
`MAX_MEMORY_CHARS` (refused with a note to shorten it). From a DM of the person
alone with the agent only into a space nobody but that person reads (what the model
writes there may carry the DM's own words, which no check counts as read; review M6
finding 16a). Through `writing.effect`: the page, its folders and the mapping commit
with the call's journal entry.
"""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.access import Action, can
from app.modules.agents import memory
from app.modules.agents.memory_repository import MemoryRepository
from app.modules.agents.scope import PlaceKind, place_of
from app.modules.agents.scope_repository import ScopeRepository
from app.modules.agents.toolbox.base import NOT_FOUND, Subject, ToolContext
from app.modules.agents.toolbox.writing import by, closed_to_ai, effect, leaks_into
from app.modules.wiki.models import MAX_CONTENT_CHARS
from app.modules.wiki.visibility import PageReader
from app.runtime.loop import ToolResult

MAX_MEMORY_CHARS = memory.MAX_MEMORY_CHARS
SHARED_SPACE = (
    "Refused (memory.shared_space): from a direct conversation alone with the person, "
    "memory goes only into a space nobody but the person reads (such as their own). "
    "What you write could carry this conversation to the others there."
)


class UpdateMemoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: uuid.UUID
    content: Annotated[str, StringConstraints(max_length=MAX_CONTENT_CHARS)]


async def update_memory(ctx: ToolContext, args: UpdateMemoryArgs) -> ToolResult:
    attrs = {"space": str(args.space_id)}
    if not await can(ctx.session, ctx.actor, Action.SPACE_READ, args.space_id) or (
        await closed_to_ai(ctx, args.space_id)
    ):
        return ToolResult("memory", NOT_FOUND, attrs)
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, args.space_id):
        return ToolResult("memory", "Not allowed here.", attrs)
    if len(args.content) > MAX_MEMORY_CHARS:
        text = (
            f"Refused (memory.too_long): a memory page holds at most {MAX_MEMORY_CHARS:,} "
            f"characters; yours has {len(args.content):,}. Shorten it and call "
            "update_memory again."
        )
        return ToolResult("memory", text, attrs)
    if why := await leaks_into(ctx, args.space_id):
        return ToolResult("memory", why, attrs)
    if await _shared_from_alone(ctx, args.space_id):
        return ToolResult("memory", SHARED_SPACE, attrs)

    async def write() -> ToolResult:
        page = await memory.write(
            ctx.session, ctx.actor, ctx.run.agent_id, args.space_id, args.content, by(ctx)
        )
        text = f"Memory saved (page id={page.id}, version {page.version})."
        return ToolResult("memory", text, attrs)

    return await effect(ctx, "memory", attrs, write)


async def _shared_from_alone(ctx: ToolContext, space_id: uuid.UUID) -> bool:
    run = ctx.run
    place = await place_of(ctx.session, run.org_id, run.conversation_id, run.user_id)
    if place is None or place.kind != PlaceKind.ALONE:
        return False
    return await ScopeRepository(ctx.session, run.org_id).read_by_others(space_id, run.user_id)


async def memory_subjects(ctx: ToolContext, args: UpdateMemoryArgs) -> list[Subject] | None:
    """The memory page as it is (its version), or the space a first one goes to."""
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, args.space_id):
        return None
    found = await MemoryRepository(ctx.session, ctx.run.org_id).get(ctx.run.agent_id, args.space_id)
    if found is not None:
        page = await PageReader(ctx.session).repo(ctx.actor).live(found.page_id)
        if page is not None and page.space_id == args.space_id:
            return [Subject("page", page.id, page.version, page.space_id)]
    return [Subject("space", args.space_id, 0, args.space_id)]
