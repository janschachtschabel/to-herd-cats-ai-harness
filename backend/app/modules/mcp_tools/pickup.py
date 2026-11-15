"""Ticket pick-up, the tools only an external agent's token gets at `/mcp` (plan M8
decision 12): they work for the token's agent, so they are not in the run catalog
(`agents/toolbox/catalog.py`), where an agent gets its tickets by assignment.

- `list_my_tickets` (level 1, reading): the tickets assigned to the agent that are not
  done or cancelled, as the token may read them (`reading.ticket_scope`, located: the
  token's scope ∩ the person's rights ∩ the agent's roles ∩ the AI policy), last
  changed first, with each one's `version`.
- `claim_ticket` (level 2): take an unassigned ticket (or one assigned to the agent
  already) and move it from `open` to the space's first `active` status
  (`tickets/claiming.py`), with the version read: of two agents claiming one ticket
  the second gets a tool error. A ticket assigned to someone else, in review, done
  or cancelled is refused.

Commenting, status changes up to review (never done) and page proposals are the
catalog's tools (`exposed.py`), written for the agent too (`context.py`).
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.principal import Principal, PrincipalType
from app.modules.agents.toolbox.base import NOT_FOUND, Effect, ToolSpec, WriteContext
from app.modules.agents.toolbox.reading import ticket_scope
from app.modules.agents.toolbox.ticket_tools import AGENT_CATEGORIES, find_ticket
from app.modules.agents.toolbox.writing import by, effect, refusal
from app.modules.mcp_tools.context import TokenContext
from app.modules.tickets.claiming import TicketClaims
from app.modules.tickets.listing import Filters, Sort
from app.modules.tickets.models import ticket_key
from app.modules.tickets.repository import TicketRepository
from app.runtime.loop import ToolResult

MY_TICKETS = 50
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


class ListMyTicketsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key
    version: Annotated[int, Field(ge=1)] | None = None


async def list_my_tickets(ctx: TokenContext, args: ListMyTicketsArgs) -> ToolResult:
    assert ctx.agent_id is not None  # offered to agent tokens only (`exposed.py`)
    filters = Filters(agent_assignee_id=ctx.agent_id, status_categories=AGENT_CATEGORIES)
    repo = TicketRepository(ctx.session, ticket_scope(ctx, located=True))
    views = await repo.page(filters, Sort.UPDATED, None, MY_TICKETS + 1)
    lines = []
    for view in views[:MY_TICKETS]:
        ticket = view.ticket
        lines.append(
            f"- ticket key={ticket_key(ticket.number)} title={ticket.title!r} "
            f"status={view.status.name!r} ({view.status.category}) "
            f"priority={ticket.priority} version={ticket.version}"
        )
    if len(views) > MY_TICKETS:
        lines.append(f"[only the {MY_TICKETS} last changed]")
    found = frozenset(view.ticket.space_id for view in views)
    return ToolResult("ticket", "\n".join(lines) or NOT_FOUND, {}, found)


async def claim_ticket(ctx: TokenContext, args: ClaimTicketArgs) -> ToolResult:
    assert ctx.agent_id is not None
    attrs = {"key": args.key}
    ticket = await find_ticket(ctx, args.key)
    if ticket is None:
        return refusal("ticket", NOT_FOUND, attrs)
    me = Principal.agent(ctx.agent_id)
    if ticket.assignee_id is not None and (
        ticket.assignee_type != PrincipalType.AGENT or ticket.assignee_id != me.id
    ):
        return refusal("ticket", "Assigned to someone else: only an unassigned ticket.", attrs)

    async def write() -> ToolResult:
        version = args.version if args.version is not None else ticket.version
        view = await TicketClaims(ctx.session).claim(ctx.actor, ticket.number, version, me, by(ctx))
        said = f"{ticket_key(ticket.number)} is yours, status {view.status.name!r}"
        return ToolResult("ticket", f"{said}, version {view.ticket.version}.", attrs)

    return await effect(ctx, "ticket", attrs, write)


async def _never(ctx: WriteContext, args: BaseModel) -> ToolResult:  # pragma: no cover
    raise AssertionError("pick-up tools run through `exposed.py`, never a run")


LIST_MY_TICKETS = ToolSpec(
    name="list_my_tickets",
    description=(
        "List the tickets assigned to you that are not done or cancelled, last changed "
        "first, with each one's key, status and version."
    ),
    args=ListMyTicketsArgs,
    run=_never,
    level=1,
    effect=Effect.READ,
)
CLAIM_TICKET = ToolSpec(
    name="claim_ticket",
    description=(
        "Take a ticket for yourself: an unassigned one (or one assigned to you) moves "
        "to the space's first status of category active. Give the version you read "
        "(list_my_tickets shows it); if the ticket changed meanwhile, read it again. "
        "Tickets of someone else, in review, done or cancelled are refused."
    ),
    args=ClaimTicketArgs,
    run=_never,
    level=2,
    effect=Effect.WRITE,
)
