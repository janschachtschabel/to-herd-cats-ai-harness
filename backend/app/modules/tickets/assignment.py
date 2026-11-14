"""Who may assign whom (plan M4 decisions 2 and 3).

- Taking an unassigned ticket (or keeping one's own) and letting go of one's own
  assignment need `ticket.edit` in the ticket's space.
- Every other assignment (someone else, or taking a ticket from someone) needs
  `ticket.assign` (403 without it).
- Only an active person of the organisation who may read tickets in the space can be
  assigned: anyone else is 422 `ticket.assignee_invalid`, the same answer for nobody,
  someone elsewhere and someone without access. Losing access later does not undo an
  assignment; it just gives no access.
- An agent (plan M6 decision 7) is assigned only with `ticket.assign`, by someone with
  `ai.use`, and only if it is no draft and a member of the space with a role that lets
  it edit tickets there (`agent_hooks.AssigneeHooks.assignable`); anything else is the
  same 422 `ticket.assignee_invalid`, so the answer reveals nothing about agents.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require, space_ids_with
from app.core.errors import ValidationFailed
from app.core.principal import Principal, PrincipalType
from app.modules.tickets.agent_hooks import assignee_hooks
from app.modules.tickets.repository import TicketRepository, TicketScope


async def check_assignment(
    session: AsyncSession,
    actor: Actor,
    repo: TicketRepository,
    space_id: uuid.UUID,
    old: Principal | None,
    new: Principal | None,
) -> None:
    await require(session, actor, assignment_action(actor.principal, old, new), space_id)
    if new is not None and not await _assignable(session, actor, repo, space_id, new):
        raise ValidationFailed("Cannot be assigned here", code="ticket.assignee_invalid")


def assignment_action(me: Principal, old: Principal | None, new: Principal | None) -> Action:
    """The right a change of assignee from `old` to `new` needs from `me`: the one rule,
    for the service and for an agent's released `assign_ticket` (`approvals/gate.py`)."""
    own = (new == me and old in (None, me)) or (new is None and old == me)
    return Action.TICKET_EDIT if own else Action.TICKET_ASSIGN


async def needed_to_assign(
    session: AsyncSession, actor: Actor, number: int, new: Principal | None
) -> Action:
    """`assignment_action` for the ticket as it is now (`ticket.assign`, the stricter,
    for one the actor does not see)."""
    scope = TicketScope(actor.org_id, space_ids_with(actor, Action.TICKET_READ))
    ticket = await TicketRepository(session, scope).by_number(number)
    if ticket is None:
        return Action.TICKET_ASSIGN
    old = None
    if ticket.assignee_type is not None and ticket.assignee_id is not None:
        old = Principal(ticket.assignee_type, ticket.assignee_id)
    return assignment_action(actor.principal, old, new)


async def _assignable(
    session: AsyncSession,
    actor: Actor,
    repo: TicketRepository,
    space_id: uuid.UUID,
    new: Principal,
) -> bool:
    if new.type == PrincipalType.USER:
        return await repo.assignable(space_id, new.id)
    hooks = assignee_hooks()
    if new.type != PrincipalType.AGENT or hooks is None:
        return False
    return await hooks.assignable(session, actor, space_id, new.id)
