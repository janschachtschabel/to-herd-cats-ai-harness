"""The first reading tools (plan M5 decision 4): `search`, `read_page`, `read_ticket`,
through the services with the run's actor (`agents/actor.py`), so the same rights
apply as for the person, narrowed to what the agent may read.

What AI may not read is left out in the statement that applies the rights (spec 7.3,
`ai/policy_filters.py`): `search` finds only pages and tickets in spaces whose policy
lets the run's connection receive them, and no page locked for AI, so nothing else
shows up even as a title or a snippet. `read_page` and `read_ticket` refuse spaces
with policy `none` and pages locked for AI; content of a `restricted` space they do
return, and the run stops with `policy_blocked` before its next model call if its
connection may not receive it (the check in `step_host.py`). Whatever a tool could
not find or may not read answers the same "not found".
"""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.access import Action, space_ids_with
from app.core.errors import NotFound
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.search.service import SearchHit, SearchService
from app.modules.spaces.models import Space
from app.modules.tickets.base import readable, view_of
from app.modules.tickets.models import ticket_key
from app.modules.tickets.repository import TicketRepository, TicketScope
from app.modules.tickets.search import key_number
from app.modules.wiki.visibility import PageReader
from app.runtime.loop import ToolResult

SEARCH_HITS = 8


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ReadPageArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: uuid.UUID


class ReadTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


async def search(ctx: ToolContext, args: SearchArgs) -> ToolResult:
    hits = await SearchService(ctx.session).for_ai(
        ctx.actor, args.query, location=ctx.location, limit=SEARCH_HITS
    )
    lines = []
    for hit in hits:
        ctx.reads.spaces.add(hit.space_id)
        if isinstance(hit, SearchHit):
            ctx.reads.pages.add(hit.id)
            lines.append(
                f"- page id={hit.id} title={hit.title!r} space={hit.space_name!r}\n  {hit.snippet}"
            )
        else:
            ctx.reads.tickets.add(hit.id)
            lines.append(
                f"- ticket key={ticket_key(hit.number)} title={hit.title!r} "
                f"kind={hit.kind} status={hit.status.name!r} space={hit.space_name!r}\n"
                f"  {hit.snippet}"
            )
    found = frozenset(hit.space_id for hit in hits)
    return ToolResult("search", "\n".join(lines) or NOT_FOUND, {"query": args.query}, found)


async def read_page(ctx: ToolContext, args: ReadPageArgs) -> ToolResult:
    try:
        page = await PageReader(ctx.session).for_ai(ctx.actor, args.page_id)
    except NotFound:
        return ToolResult("wiki", NOT_FOUND, {"id": str(args.page_id)})
    ctx.reads.spaces.add(page.space_id)
    ctx.reads.pages.add(page.id)
    text = f"# {page.title}\n\n{page.content_md}"
    return ToolResult("wiki", text, {"id": str(page.id)}, frozenset({page.space_id}))


async def read_ticket(ctx: ToolContext, args: ReadTicketArgs) -> ToolResult:
    number = key_number(args.key)
    if number is None:
        return ToolResult("ticket", NOT_FOUND, {"key": args.key})
    repo = TicketRepository(ctx.session, ticket_scope(ctx))
    try:
        ticket = await readable(ctx.session, ctx.actor, repo, number)
        view = await view_of(ctx.session, ctx.actor, repo, ticket.id)
    except NotFound:
        return ToolResult("ticket", NOT_FOUND, {"key": args.key})
    ctx.reads.spaces.add(ticket.space_id)
    ctx.reads.tickets.add(ticket.id)
    fields = [
        f"key: {ticket_key(ticket.number)}",
        f"title: {ticket.title}",
        f"kind: {ticket.kind}",
        f"status: {view.status.name} ({view.status.category})",
        f"priority: {ticket.priority}",
        f"assignee: {view.assignee_name or '-'}",
        f"reporter: {view.reporter_name or '-'}",
        f"due: {ticket.due_on.isoformat() if ticket.due_on else '-'}",
        f"parent: {ticket_key(view.parent.number) if view.parent else '-'}",
        f"tags: {', '.join(tag.name for tag in view.tags) or '-'}",
    ]
    text = "\n".join(fields) + "\n\n" + ticket.description_md
    attrs = {"key": ticket_key(ticket.number)}
    return ToolResult("ticket", text, attrs, frozenset({ticket.space_id}))


def ticket_scope(ctx: ToolContext) -> TicketScope:
    """The spaces where the run may read tickets, without those AI may not read."""
    spaces = space_ids_with(ctx.actor, Action.TICKET_READ).where(
        Space.id.in_(ai_space_ids(ctx.actor.org_id))
    )
    return TicketScope(ctx.actor.org_id, spaces)
