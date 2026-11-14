"""The tools of a level-1 run, executed (plan M5 decision 4): `search`, `read_page`,
`read_ticket`, read only, through the services with the run's actor
(`agents/actor.py`), so the same rights apply as for the person, narrowed to what the
agent may read.

What AI may not read is left out in the statement that applies the rights (spec 7.3,
`ai/policy_filters.py`): `search` finds only pages and tickets in spaces whose policy
lets the run's connection receive them, and no page locked for AI, so nothing else
shows up even as a title or a snippet. `read_page` and `read_ticket` refuse spaces
with policy `none` and pages locked for AI; content of a `restricted` space they do
return, and the run stops with `policy_blocked` before its next model call if its
connection may not receive it (the check in `executor.py`). Whatever a tool could not
find or may not read answers the same "not found".

The result's text is complete here; the loop frames and cuts it for the model, the
run's event keeps all of it.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, space_ids_with
from app.core.errors import NotFound
from app.modules.agents.actor import Reads
from app.modules.ai.models import DataLocation
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.search.service import SearchHit, SearchService
from app.modules.spaces.models import Space
from app.modules.tickets.base import readable, view_of
from app.modules.tickets.models import ticket_key
from app.modules.tickets.repository import TicketRepository, TicketScope
from app.modules.tickets.search import key_number
from app.modules.wiki.visibility import PageReader
from app.runtime import tools
from app.runtime.loop import ToolResult

SEARCH_HITS = 8
NOT_FOUND = "Nothing found (or not readable)."


class RunTools:
    def __init__(
        self, session: AsyncSession, actor: Actor, location: DataLocation, reads: Reads
    ) -> None:
        self.session = session
        self.actor = actor
        self.location = location
        self.reads = reads

    async def run(self, args: tools.ToolArgs) -> ToolResult:
        if isinstance(args, tools.SearchArgs):
            return await self._search(args.query)
        if isinstance(args, tools.ReadPageArgs):
            return await self._page(args.page_id)
        return await self._ticket(args.key)

    async def _search(self, query: str) -> ToolResult:
        hits = await SearchService(self.session).for_ai(
            self.actor, query, location=self.location, limit=SEARCH_HITS
        )
        lines = []
        for hit in hits:
            self.reads.spaces.add(hit.space_id)
            if isinstance(hit, SearchHit):
                self.reads.pages.add(hit.id)
                lines.append(
                    f"- page id={hit.id} title={hit.title!r} space={hit.space_name!r}\n"
                    f"  {hit.snippet}"
                )
            else:
                self.reads.tickets.add(hit.id)
                lines.append(
                    f"- ticket key={ticket_key(hit.number)} title={hit.title!r} "
                    f"kind={hit.kind} status={hit.status.name!r} space={hit.space_name!r}\n"
                    f"  {hit.snippet}"
                )
        found = frozenset(hit.space_id for hit in hits)
        return ToolResult("search", "\n".join(lines) or NOT_FOUND, {"query": query}, found)

    async def _page(self, page_id: uuid.UUID) -> ToolResult:
        try:
            page = await PageReader(self.session).for_ai(self.actor, page_id)
        except NotFound:
            return ToolResult("wiki", NOT_FOUND, {"id": str(page_id)})
        self.reads.spaces.add(page.space_id)
        self.reads.pages.add(page.id)
        text = f"# {page.title}\n\n{page.content_md}"
        return ToolResult("wiki", text, {"id": str(page.id)}, frozenset({page.space_id}))

    async def _ticket(self, key: str) -> ToolResult:
        number = key_number(key)
        if number is None:
            return ToolResult("ticket", NOT_FOUND, {"key": key})
        repo = TicketRepository(self.session, self._ticket_scope())
        try:
            ticket = await readable(self.session, self.actor, repo, number)
            view = await view_of(self.session, self.actor, repo, ticket.id)
        except NotFound:
            return ToolResult("ticket", NOT_FOUND, {"key": key})
        self.reads.spaces.add(ticket.space_id)
        self.reads.tickets.add(ticket.id)
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

    def _ticket_scope(self) -> TicketScope:
        """The spaces where the run may read tickets, without those AI may not read."""
        spaces = space_ids_with(self.actor, Action.TICKET_READ).where(
            Space.id.in_(ai_space_ids(self.actor.org_id))
        )
        return TicketScope(self.actor.org_id, spaces)
