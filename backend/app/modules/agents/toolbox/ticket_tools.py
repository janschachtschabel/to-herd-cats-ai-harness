"""The tickets' writing tools (plan M6 decisions 3 and 7; spec 8.6 and 10).

A ticket is found as the run may read it and AI may (`reading.ticket_scope`: not in a
space whose policy is `none`; anything else answers "not found" like a free key), and
changed through `TicketService` with the run's actor (its `ticket.*` rights in the
space, within the run's write scope), written for the agent (`writing.by`): the
ticket's events and timeline entries name the agent and the run.

- `comment_ticket` (level 2): an agent message in the ticket's thread.
- `set_ticket_status` (level 2): a status of the ticket's space of category `open`,
  `active` or at most `review`; `done` and `cancelled` are a person's (spec 10), a
  clear refusal otherwise (checked again on the status as the change holds it).
- `create_ticket` (level 2), `link_ticket_page` (level 2: a page AI may read).
- `assign_ticket` (level 3): to a person or an agent (`ticket.assign`), with a reason
  that goes into the ticket's thread as the agent's comment. To an agent it hands the
  ticket over: that agent's run starts on it (`agents/triggers.py`). A run that came
  through `MAX_CHAIN_DEPTH` handovers hands over no more: the tool refuses
  (`run.handover_limit`) and the thread notes it (`run.refused`).

Every write goes through `writing.effect` (one savepoint; the audience check first,
except for a link, which shows nothing of either side to whoever cannot see it).
"""

import hashlib
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.access import Action, can
from app.core.errors import NotFound, ValidationFailed
from app.core.principal import Principal, PrincipalType
from app.modules.agents.models import MAX_CHAIN_DEPTH
from app.modules.agents.notices import notice
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.standing import Refusal
from app.modules.agents.toolbox.base import NOT_FOUND, Subject, ToolContext
from app.modules.agents.toolbox.reading import ticket_scope
from app.modules.agents.toolbox.writing import LEAKS, by, effect, key_for, leaks_into, refused
from app.modules.agents.triggers import REFUSED_KEY
from app.modules.ai.models import AiPolicy
from app.modules.messaging.models import MAX_BODY_CHARS
from app.modules.messaging.service import MessageService
from app.modules.tickets.base import readable
from app.modules.tickets.links import TicketLinks
from app.modules.tickets.models import (
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
    Priority,
    StatusCategory,
    TicketKind,
    WorkItem,
    ticket_key,
)
from app.modules.tickets.repository import TicketRepository
from app.modules.tickets.search import key_number
from app.modules.tickets.service import TicketService
from app.modules.tickets.statuses import status_repository
from app.modules.wiki.visibility import PageReader
from app.runtime.loop import ToolResult

AGENT_CATEGORIES = (StatusCategory.OPEN, StatusCategory.ACTIVE, StatusCategory.REVIEW)
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_BODY_CHARS)
]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CommentTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key
    text: Text


class SetTicketStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class CreateTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: uuid.UUID
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_CHARS)
    ]
    description_md: Annotated[str, StringConstraints(max_length=MAX_DESCRIPTION_CHARS)] = ""
    kind: TicketKind = TicketKind.TASK
    priority: Priority = Priority.NORMAL
    parent_key: Key | None = None


class LinkTicketPageArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key
    page_id: uuid.UUID


class AssignTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key
    assignee_type: Literal["user", "agent"]
    assignee_id: uuid.UUID
    reason: Reason


async def comment_ticket(ctx: ToolContext, args: CommentTicketArgs) -> ToolResult:
    attrs = {"key": args.key}
    ticket = await _ticket(ctx, args.key)
    if ticket is None:
        return ToolResult("ticket", NOT_FOUND, attrs)
    if await leaks_into(ctx, ticket.space_id):
        return ToolResult("ticket", LEAKS, attrs)

    async def write() -> ToolResult:
        await _comment(ctx, ticket, args.text, "comment")
        return ToolResult("ticket", f"Commented on {ticket_key(ticket.number)}.", attrs)

    return await effect(ctx, "ticket", attrs, write)


async def set_ticket_status(ctx: ToolContext, args: SetTicketStatusArgs) -> ToolResult:
    attrs = {"key": args.key}
    ticket = await _ticket(ctx, args.key)
    if ticket is None:
        return ToolResult("ticket", NOT_FOUND, attrs)
    statuses = await status_repository(ctx.session, ctx.actor).in_space(ticket.space_id)
    wanted = args.status.casefold()
    status = next((s for s in statuses if s.name.casefold() == wanted or str(s.id) == wanted), None)
    allowed = [s for s in statuses if s.category in AGENT_CATEGORIES]
    if status is None or status.category not in AGENT_CATEGORIES:
        names = ", ".join(f"{s.name!r} ({s.category})" for s in allowed)
        why = (
            "Not a status of this ticket's space"
            if status is None
            else ("Only a person sets a status of category done or cancelled")
        )
        return ToolResult("ticket", f"{why}. You may set: {names}.", attrs)

    async def write() -> ToolResult:
        view = await TicketService(ctx.session).update(
            ctx.actor, ticket.number, ticket.version, {"status_id": status.id}, by(ctx)
        )
        if view.status.category not in AGENT_CATEGORIES:  # changed its category meanwhile
            raise ValidationFailed(code="ticket.status_not_for_agents")
        return ToolResult(
            "ticket", f"{ticket_key(ticket.number)} is now {view.status.name!r}.", attrs
        )

    return await effect(ctx, "ticket", attrs, write)


async def create_ticket(ctx: ToolContext, args: CreateTicketArgs) -> ToolResult:
    attrs = {"space": str(args.space_id)}
    policies = await ReadRepository(ctx.session, ctx.run.org_id).policies({args.space_id})
    if not await can(ctx.session, ctx.actor, Action.TICKET_READ, args.space_id) or any(
        p.kind == AiPolicy.NONE for p in policies
    ):
        return ToolResult("ticket", NOT_FOUND, attrs)
    if await leaks_into(ctx, args.space_id):
        return ToolResult("ticket", LEAKS, attrs)
    parent_id = None
    if args.parent_key is not None:
        parent = await _ticket(ctx, args.parent_key)
        if parent is None:
            return ToolResult("ticket", NOT_FOUND, {"key": args.parent_key})
        parent_id = parent.id

    async def write() -> ToolResult:
        view = await TicketService(ctx.session).create(
            ctx.actor,
            args.space_id,
            title=args.title,
            description_md=args.description_md,
            kind=args.kind,
            priority=args.priority,
            parent_id=parent_id,
            by=by(ctx),
        )
        return ToolResult("ticket", f"Created {ticket_key(view.ticket.number)}.", attrs)

    return await effect(ctx, "ticket", attrs, write)


async def link_ticket_page(ctx: ToolContext, args: LinkTicketPageArgs) -> ToolResult:
    attrs = {"key": args.key, "page": str(args.page_id)}
    ticket = await _ticket(ctx, args.key)
    try:
        page = await PageReader(ctx.session).for_ai(ctx.actor, args.page_id)
    except NotFound:
        page = None
    if ticket is None or page is None:
        return ToolResult("ticket", NOT_FOUND, attrs)

    async def write() -> ToolResult:
        linked = await TicketLinks(ctx.session).link(ctx.actor, ticket.number, page.id, by(ctx))
        said = "Linked" if linked else "Already linked"
        return ToolResult(
            "ticket", f"{said}: {ticket_key(ticket.number)} and page id={page.id}.", attrs
        )

    return await effect(ctx, "ticket", attrs, write)


async def assign_ticket(ctx: ToolContext, args: AssignTicketArgs) -> ToolResult:
    attrs = {"key": args.key}
    ticket = await _ticket(ctx, args.key)
    if ticket is None:
        return ToolResult("ticket", NOT_FOUND, attrs)
    if await leaks_into(ctx, ticket.space_id):
        return ToolResult("ticket", LEAKS, attrs)
    assignee = Principal(PrincipalType(args.assignee_type), args.assignee_id)
    if assignee.type == PrincipalType.AGENT and ctx.run.chain_depth >= MAX_CHAIN_DEPTH:
        return await _handover_refused(ctx, ticket, assignee.id)

    async def write() -> ToolResult:
        await TicketService(ctx.session).update(
            ctx.actor, ticket.number, ticket.version, {"assignee": assignee}, by(ctx)
        )
        await _comment(ctx, ticket, args.reason, "assign")
        return ToolResult("ticket", f"Assigned {ticket_key(ticket.number)}.", attrs)

    return await effect(ctx, "ticket", attrs, write)


async def _handover_refused(ctx: ToolContext, ticket: WorkItem, agent_id: uuid.UUID) -> ToolResult:
    """The ticket stays as it is; its thread notes the handover that did not happen
    (the handing agent as the entry's actor)."""
    thread = await TicketService(ctx.session).thread(ctx.actor, ticket)
    content = {
        "key": REFUSED_KEY,
        "actor": str(ctx.run.agent_id),
        "to": Refusal.HANDOVER_LIMIT.value,
    }
    key = key_for(ctx, "handover", ticket.id, agent_id)
    await notice(ctx.session, ctx.run.org_id, ctx.run.agent_id, thread, key, content)
    return refused("ticket", Refusal.HANDOVER_LIMIT.value, {"key": ticket_key(ticket.number)})


# --- what a call changes (a release is bound to it, `approvals/gate.py`) -------------


async def ticket_subjects(ctx: ToolContext, args: CommentTicketArgs) -> list[Subject] | None:
    """For every tool that changes one ticket, named by `key`."""
    ticket = await _ticket(ctx, args.key)
    return None if ticket is None else [_subject(ticket)]


async def create_subjects(ctx: ToolContext, args: CreateTicketArgs) -> list[Subject] | None:
    if not await can(ctx.session, ctx.actor, Action.TICKET_READ, args.space_id):
        return None
    return [Subject("space", args.space_id, 0, args.space_id)]


async def link_subjects(ctx: ToolContext, args: LinkTicketPageArgs) -> list[Subject] | None:
    ticket = await _ticket(ctx, args.key)
    try:
        page = await PageReader(ctx.session).for_ai(ctx.actor, args.page_id)
    except NotFound:
        return None
    if ticket is None:
        return None
    return [_subject(ticket), Subject("page", page.id, page.version, page.space_id)]


def _subject(ticket: WorkItem) -> Subject:
    return Subject("ticket", ticket.id, ticket.version, ticket.space_id)


async def _ticket(ctx: ToolContext, key: str) -> WorkItem | None:
    number = key_number(key)
    if number is None:
        return None
    try:
        return await readable(
            ctx.session, ctx.actor, TicketRepository(ctx.session, ticket_scope(ctx)), number
        )
    except NotFound:
        return None


async def _comment(ctx: ToolContext, ticket: WorkItem, text: str, kind: str) -> None:
    """The agent's message in the ticket's thread (one per run, ticket and text)."""
    thread = await TicketService(ctx.session).thread(ctx.actor, ticket)
    digest = hashlib.sha256(text.encode()).hexdigest()
    key = key_for(ctx, kind, ticket.id, digest)
    await MessageService(ctx.session).post(ctx.actor, thread.id, text, client_id=key, by=by(ctx))
