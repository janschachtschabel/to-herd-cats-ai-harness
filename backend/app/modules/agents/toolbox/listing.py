"""The listing tools of level 1 (plan M6 task 4): `list_tree`, `list_versions`,
`search_tickets`, through the services with the run's actor, like `reading.py`.

Like `search`, the lists leave out in the statement what the run's connection may not
receive (spaces whose policy does not allow its location, pages locked for AI), so
nothing of it shows up even as a title; `list_versions` refuses a page `read_page`
refuses. Whatever a tool could not find or may not read answers the same "not found".
Each names the spaces it read from (the event's `spaces`); a list of spaces names
none, as it shows only their names.
"""

import uuid
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.pagination import PageParams
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.agents.toolbox.reading import ticket_scope
from app.modules.ai.policy_filters import ai_page_ids, ai_space_ids
from app.modules.spaces.service import SpaceService
from app.modules.tickets.listing import Filters, Sort
from app.modules.tickets.models import Priority, StatusCategory, TicketKind, ticket_key
from app.modules.tickets.repository import TicketRepository
from app.modules.wiki.models import PageStatus
from app.modules.wiki.service import PageService
from app.modules.wiki.versions import VersionService
from app.modules.wiki.visibility import PageReader
from app.runtime.loop import ToolResult

TREE_PAGES = 100
SPACES = 100
VERSIONS = 30
TICKET_HITS = 20
INVALID_CURSOR = "Invalid cursor."

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ListTreeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: uuid.UUID | None = None
    cursor: Annotated[str, StringConstraints(max_length=500)] | None = None


class ListVersionsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: uuid.UUID


class SearchTicketsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Query | None = None
    status: list[StatusCategory] = Field(default_factory=list, max_length=len(StatusCategory))
    assigned_to_me: bool = False
    unassigned: bool = False
    kind: TicketKind | None = None
    priority: Priority | None = None
    space_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _either(self) -> Self:
        if self.assigned_to_me and self.unassigned:
            raise ValueError("assigned_to_me or unassigned, not both")
        return self


async def list_tree(ctx: ToolContext, args: ListTreeArgs) -> ToolResult:
    if args.space_id is None:
        return await _spaces(ctx)
    attrs = {"space": str(args.space_id)}
    params = PageParams(limit=TREE_PAGES, cursor=args.cursor)
    only = ai_page_ids(ctx.actor.org_id, ctx.location)
    try:
        listed = await PageService(ctx.session).tree(ctx.actor, args.space_id, params, among=only)
    except NotFound:
        return ToolResult("wiki", NOT_FOUND, attrs)
    except ValidationFailed:
        return ToolResult("wiki", INVALID_CURSOR, attrs)
    if not listed.items:
        return ToolResult("wiki", NOT_FOUND, attrs)
    ctx.reads.spaces.add(args.space_id)
    lines = [
        f"- page id={p.id} path={p.path!r} title={p.title!r}"
        + (" (draft)" if p.status != PageStatus.PUBLISHED else "")
        for p in listed.items
    ]
    if listed.next_cursor:
        attrs["next_cursor"] = listed.next_cursor
        lines.append("(more pages: call again with this cursor)")
    return ToolResult("wiki", "\n".join(lines), attrs, frozenset({args.space_id}))


async def _spaces(ctx: ToolContext) -> ToolResult:
    """The spaces the run may read whose policy lets its connection receive them."""
    listed = await SpaceService(ctx.session).list_visible(
        ctx.actor,
        PageParams(limit=SPACES),
        include_others_personal=False,
        among=ai_space_ids(ctx.actor.org_id, ctx.location),
    )
    lines = [f"- space id={s.id} name={s.name!r} kind={s.kind}" for s in listed.items]
    if listed.next_cursor:
        lines.append(f"(only the first {SPACES} spaces)")
    return ToolResult("wiki", "\n".join(lines) or NOT_FOUND)


async def list_versions(ctx: ToolContext, args: ListVersionsArgs) -> ToolResult:
    """The page's versions, newest first, without their content (the history needs
    the right to edit, as for a person: spec 9, review R16)."""
    attrs = {"id": str(args.page_id)}
    try:
        page = await PageReader(ctx.session).for_ai(ctx.actor, args.page_id)
        listed = await VersionService(ctx.session).list(
            ctx.actor, page.id, PageParams(limit=VERSIONS)
        )
    except (NotFound, Forbidden):
        return ToolResult("wiki", NOT_FOUND, attrs)
    ctx.reads.spaces.add(page.space_id)
    ctx.reads.pages.add(page.id)
    lines = []
    for named in listed.items:
        v = named.version
        line = (
            f"- version {v.number} at {v.created_at:%Y-%m-%d %H:%M} "
            f"by {named.author_name or 'an agent'} source={v.source}"
        )
        if v.label:
            line += f" label={v.label!r}"
        if v.change_summary:
            line += f" summary={v.change_summary!r}"
        lines.append(line)
    if listed.next_cursor:
        lines.append(f"(only the newest {VERSIONS} versions)")
    text = f"# {page.title}\n" + "\n".join(lines)
    return ToolResult("wiki", text, attrs, frozenset({page.space_id}))


async def search_tickets(ctx: ToolContext, args: SearchTicketsArgs) -> ToolResult:
    """Tickets by text and filters, last changed first."""
    filters = Filters(
        space_id=args.space_id,
        status_categories=tuple(args.status),
        assignee_id=ctx.actor.principal.id if args.assigned_to_me else None,
        unassigned=args.unassigned,
        kind=args.kind,
        priority=args.priority,
        q=args.query,
    )
    repo = TicketRepository(ctx.session, ticket_scope(ctx, located=True))
    views = await repo.page(filters, Sort.UPDATED, None, TICKET_HITS)
    lines = []
    for view in views:
        ticket = view.ticket
        ctx.reads.spaces.add(ticket.space_id)
        ctx.reads.tickets.add(ticket.id)
        lines.append(
            f"- ticket key={ticket_key(ticket.number)} title={ticket.title!r} "
            f"kind={ticket.kind} status={view.status.name!r} ({view.status.category}) "
            f"priority={ticket.priority} assignee={view.assignee_name or '-'}"
        )
    found = frozenset(view.ticket.space_id for view in views)
    attrs = {"query": args.query} if args.query else {}
    return ToolResult("ticket", "\n".join(lines) or NOT_FOUND, attrs, found)
