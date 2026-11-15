"""What every ticket service shares: the actor's view of the tickets, finding a ticket
it may see (404 `ticket.not_found` otherwise, the same as for a free number), taking
one for a change (`ticket.edit`, the version read, the row locked), emitting the
change's event, and the views a ticket is shown with (its tags included, one query
for any number of tickets)."""

import dataclasses
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require, space_ids_with
from app.core.authorship import Authorship, acting
from app.core.errors import Conflict, NotFound
from app.core.principal import PrincipalType
from app.modules.messaging.agent_hooks import agent_hooks
from app.modules.tags.models import SubjectType
from app.modules.tags.repository import tag_repository
from app.modules.tickets.events import Changes, ticket_event
from app.modules.tickets.models import StatusCategory, WorkItem
from app.modules.tickets.repository import TicketRepository, TicketScope, TicketView
from app.modules.tickets.sprint_repository import FINISHED, SprintRepository
from app.modules.tickets.thread_repository import TicketThreadRepository


def ticket_not_found() -> NotFound:
    return NotFound(code="ticket.not_found")


def ticket_repository(session: AsyncSession, actor: Actor) -> TicketRepository:
    """The actor's view of the tickets: the spaces where it may read them."""
    scope = TicketScope(actor.org_id, space_ids_with(actor, Action.TICKET_READ))
    return TicketRepository(session, scope)


async def readable(
    session: AsyncSession, actor: Actor, repo: TicketRepository, number: int, *, lock: bool = False
) -> WorkItem:
    """The ticket if the actor may see it (with `lock`: as committed now, locked)."""
    ticket = await repo.by_number(number, lock=lock)
    if ticket is None:
        raise ticket_not_found()
    try:  # also notes an admin's look into a team or personal space (spec 5.5)
        await require(session, actor, Action.TICKET_READ, ticket.space_id)
    except NotFound:
        raise ticket_not_found() from None
    return ticket


async def editable(
    session: AsyncSession,
    actor: Actor,
    number: int,
    version: int | None = None,
    *,
    parent_id: uuid.UUID | None = None,
) -> tuple[TicketRepository, WorkItem]:
    """The ticket, locked, for a change: `ticket.edit` (403), and, with `version`, the
    version the client read (409 `ticket.version_conflict`).

    With the `parent_id` the change sets, the two rows are locked in the order of their
    ids (review M4 P2): a parent with the lower id is held (`FOR SHARE`) before the
    ticket, otherwise after it (`_check_hierarchy`). Two tickets made each other's
    parent at once then wait for each other in turn instead of deadlocking, and the
    second sees the first's change."""
    repo = ticket_repository(session, actor)
    if parent_id is not None:
        found = await repo.by_number(number)
        if found is not None and parent_id < found.id:
            await repo.parent_in(found.space_id, parent_id)
    ticket = await readable(session, actor, repo, number, lock=True)
    await require(session, actor, Action.TICKET_EDIT, ticket.space_id)
    if version is not None and ticket.version != version:
        raise Conflict(code="ticket.version_conflict", details={"current_version": ticket.version})
    return repo, ticket


async def emit_change(
    session: AsyncSession,
    actor: Actor,
    type_: str,
    ticket: WorkItem,
    changes: Changes,
    by: Authorship | None = None,
) -> None:
    """The change's one event, naming the ticket's thread; `by`: written for an agent
    (its run), which the event names as its actor."""
    thread = await TicketThreadRepository(session, actor.org_id).thread_for(ticket)
    await ticket_event(
        session,
        acting(actor, by),
        type_,
        ticket_id=ticket.id,
        space_id=ticket.space_id,
        conversation_id=thread.id,
        changes=changes,
        run_id=by.run_id if by else None,
    )


async def with_tags(
    session: AsyncSession, actor: Actor, views: Sequence[TicketView]
) -> list[TicketView]:
    """The views with the tickets' tags, in one query (tickets the actor has read)."""
    if not views:
        return []
    tags = await tag_repository(session, actor).tags_for(
        SubjectType.TICKET, [v.ticket.id for v in views]
    )
    agents = await agent_names(session, actor.org_id, views)
    waiting = await awaiting_pickup(session, actor.org_id, views)
    return [
        dataclasses.replace(
            v,
            tags=tuple(tags.get(v.ticket.id, ())),
            awaiting_pickup=v.ticket.id in waiting,
            assignee_name=_name(v.ticket.assignee_type, v.ticket.assignee_id, agents)
            or v.assignee_name,
            reporter_name=_name(v.ticket.reporter_type, v.ticket.reporter_id, agents)
            or v.reporter_name,
        )
        for v in views
    ]


async def agent_names(
    session: AsyncSession, org_id: uuid.UUID, views: Sequence[TicketView]
) -> dict[uuid.UUID, str]:
    """The names of the agents the views name as assignee or reporter (plan M6
    decision 7); people's names come with the views."""
    ids = {
        pid
        for v in views
        for ptype, pid in (
            (v.ticket.assignee_type, v.ticket.assignee_id),
            (v.ticket.reporter_type, v.ticket.reporter_id),
        )
        if ptype == PrincipalType.AGENT and pid is not None
    }
    return await agent_hooks().names(session, org_id, ids) if ids else {}


async def awaiting_pickup(
    session: AsyncSession, org_id: uuid.UUID, views: Sequence[TicketView]
) -> set[uuid.UUID]:
    """The tickets (ids) that wait for an external agent to pick them up (plan M8
    decision 12): assigned to one and still in a status of category `open`."""
    candidates = {
        v.ticket.id: v.ticket.assignee_id
        for v in views
        if v.ticket.assignee_type == PrincipalType.AGENT
        and v.ticket.assignee_id is not None
        and v.status.category == StatusCategory.OPEN
    }
    if not candidates:
        return set()
    external = await agent_hooks().external_ids(session, org_id, set(candidates.values()))
    return {ticket_id for ticket_id, agent_id in candidates.items() if agent_id in external}


def _name(
    ptype: PrincipalType | None, pid: uuid.UUID | None, agents: dict[uuid.UUID, str]
) -> str | None:
    return agents.get(pid) if ptype == PrincipalType.AGENT and pid is not None else None


async def view_of(
    session: AsyncSession, actor: Actor, repo: TicketRepository, ticket_id: uuid.UUID
) -> TicketView:
    """A ticket the actor has read, as shown."""
    view = await repo.view(ticket_id)
    if view is None:  # only if it went away after the check
        raise ticket_not_found()
    (shown,) = await with_tags(session, actor, [view])
    return shown


async def leaves_closed_sprint(
    session: AsyncSession, actor: Actor, sprint_id: uuid.UUID | None, category: StatusCategory
) -> bool:
    """Whether a ticket of sprint `sprint_id` that goes to a status of `category`
    returns to the backlog: reopened (an unfinished category) in a closed sprint
    (module review M4b, finding 3)."""
    if sprint_id is None or category in FINISHED:
        return False
    sprints = SprintRepository(session, ticket_repository(session, actor).scope)
    return bool(await sprints.closed_among({sprint_id}))
