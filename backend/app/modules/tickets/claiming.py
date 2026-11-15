"""An agent takes a ticket for itself (plan M8 decision 12: an external agent's
`claim_ticket` through `/mcp`).

- The actor needs `ticket.edit` in the ticket's space and the version it read (409
  `ticket.version_conflict` otherwise), as for every change (`base.editable`, the row
  locked): of two agents claiming one ticket at once, the second waits for the first
  and finds it changed.
- Only an unassigned ticket, or one assigned to the claimant already, can be claimed
  (409 `ticket.taken`), and only while its status is of category `open` or `active`
  (422 `ticket.not_claimable`: in review, done or cancelled).
- The claimant must be an agent that may work on tickets there: no draft, a member
  of the space with a role that edits tickets (`agent_hooks.claimable`; 422
  `ticket.assignee_invalid` otherwise).
- An `open` ticket moves to the space's first status of category `active` (if the
  space has one); the assignment and the status change are one change: one version,
  one event (written for `by`), audited and handed to the agents' hooks like any
  assignment (`TicketService.after_changes`; an external agent starts no run).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.authorship import Authorship
from app.core.errors import Conflict, ValidationFailed
from app.core.principal import Principal, PrincipalType
from app.modules.tickets.agent_hooks import assignee_hooks
from app.modules.tickets.base import editable, emit_change, view_of
from app.modules.tickets.events import TICKET_UPDATED, Field
from app.modules.tickets.models import StatusCategory
from app.modules.tickets.repository import TicketView
from app.modules.tickets.service import TicketService
from app.modules.tickets.statuses import status_repository

CLAIMABLE = (StatusCategory.OPEN, StatusCategory.ACTIVE)


class TicketClaims:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(
        self, actor: Actor, number: int, version: int, claimant: Principal, by: Authorship
    ) -> TicketView:
        repo, ticket = await editable(self.session, actor, number, version)
        old = None
        if ticket.assignee_type is not None and ticket.assignee_id is not None:
            old = Principal(ticket.assignee_type, ticket.assignee_id)
        if old not in (None, claimant):
            raise Conflict(code="ticket.taken")
        statuses = status_repository(self.session, actor)
        current = await statuses.lock_for_use(ticket.space_id, ticket.status_id)
        if current is None or current.category not in CLAIMABLE:
            raise ValidationFailed(code="ticket.not_claimable")
        if old is None and not await self._claimable(actor, ticket.space_id, claimant):
            raise ValidationFailed("Cannot be assigned here", code="ticket.assignee_invalid")
        changes: dict[Field, tuple[Any, Any]] = {}
        status = None
        if current.category == StatusCategory.OPEN:
            status = await statuses.first_of(ticket.space_id, StatusCategory.ACTIVE)
            if status is not None:
                changes[Field.STATUS] = (ticket.status_id, status.id)
                ticket.status_id = status.id
        if old is None:
            changes[Field.ASSIGNEE] = (None, claimant.id)
            ticket.assignee_type, ticket.assignee_id = claimant.type, claimant.id
        if not changes:
            return await view_of(self.session, actor, repo, ticket.id)
        ticket.version += 1
        await self.session.flush()
        await emit_change(self.session, actor, TICKET_UPDATED, ticket, changes, by)
        await TicketService(self.session).after_changes(actor, ticket, changes, status, by)
        return await view_of(self.session, actor, repo, ticket.id)

    async def _claimable(self, actor: Actor, space_id: uuid.UUID, claimant: Principal) -> bool:
        hooks = assignee_hooks()
        if claimant.type != PrincipalType.AGENT or hooks is None:
            return False
        return await hooks.claimable(self.session, actor, space_id, claimant.id)
