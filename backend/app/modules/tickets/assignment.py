"""Who may assign whom (plan M4 decisions 2 and 3).

- Taking an unassigned ticket (or keeping one's own) and letting go of one's own
  assignment need `ticket.edit` in the ticket's space.
- Every other assignment (someone else, or taking a ticket from someone) needs
  `ticket.assign` (403 without it).
- Only an active person of the organisation who may read tickets in the space can be
  assigned: anyone else is 422 `ticket.assignee_invalid`, the same answer for nobody,
  someone elsewhere and someone without access. Losing access later does not undo an
  assignment; it just gives no access.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.errors import ValidationFailed
from app.core.principal import Principal
from app.modules.tickets.repository import TicketRepository


async def check_assignment(
    session: AsyncSession,
    actor: Actor,
    repo: TicketRepository,
    space_id: uuid.UUID,
    old: Principal | None,
    new: Principal | None,
) -> None:
    me = actor.principal
    own = (new == me and old in (None, me)) or (new is None and old == me)
    await require(session, actor, Action.TICKET_EDIT if own else Action.TICKET_ASSIGN, space_id)
    if new is not None and not await repo.assignable(space_id, new.id):
        raise ValidationFailed("Cannot be assigned here", code="ticket.assignee_invalid")
