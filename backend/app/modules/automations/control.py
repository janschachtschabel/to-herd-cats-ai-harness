"""Pausing, resuming and deleting an automation (plan M7 decisions 12 to 14): its
owner, the managers of its place's space (`space.manage`) and `agent.manage` may (403
`automation.not_allowed` for others who see it; 404 for who does not). Each names the
version read (409 `automation.version_conflict`), bumps it and is audited (ids only).

- Pause: an active one (409 `automation.not_active` otherwise) is paused `manual`; it
  keeps its next term.
- Resume: a paused one (409 `automation.not_paused` otherwise) runs again, its
  failures counted anew; a term it missed while paused fires once (decision 5). One
  whose owner may no longer run it (`standing.owner_may_run`) is not resumed (409
  `automation.owner_unable`): it would only pause again; whoever could make it
  takes it over instead.
- Delete: the row stays as `deleted`, so its runs, their journal and its log remain
  as history; the API shows it no more and nothing fires it again. A run already
  open ends as it would have (it is the owner's request in progress; the run view
  can cancel it).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Conflict, Forbidden
from app.modules.agents.repository import AgentRepository
from app.modules.audit.recorder import record
from app.modules.automations.models import Automation, AutomationState, PausedReason
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.service import AutomationService, AutomationView
from app.modules.automations.standing import owner_may_run


class AutomationControl:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.service = AutomationService(session)

    async def pause(self, actor: Actor, automation_id: uuid.UUID, version: int) -> AutomationView:
        automation = await self._controlled(actor, automation_id, version)
        if automation.state != AutomationState.ACTIVE:
            raise Conflict(code="automation.not_active")
        await AutomationRepository(self.session, actor.org_id).pause(
            automation, PausedReason.MANUAL
        )
        await self._audit(actor, "automation.paused", automation)
        return await self.service.get(actor, automation.id)

    async def resume(self, actor: Actor, automation_id: uuid.UUID, version: int) -> AutomationView:
        automation = await self._controlled(actor, automation_id, version)
        if automation.state != AutomationState.PAUSED:
            raise Conflict(code="automation.not_paused")
        agent = await AgentRepository(self.session, actor.org_id).get(automation.agent_id)
        assert agent is not None  # the automation goes with its agent
        place = await AutomationRepository(self.session, actor.org_id).place(automation)
        if not await owner_may_run(self.session, automation.owner_user_id, agent, place):
            raise Conflict(code="automation.owner_unable")
        automation.state = AutomationState.ACTIVE
        automation.paused_reason = None
        automation.failures = 0
        automation.version += 1
        await self.session.flush()
        await self._audit(actor, "automation.resumed", automation)
        return await self.service.get(actor, automation.id)

    async def delete(self, actor: Actor, automation_id: uuid.UUID, version: int) -> None:
        automation = await self._controlled(actor, automation_id, version)
        automation.state = AutomationState.DELETED
        automation.paused_reason = None
        automation.version += 1
        await self.session.flush()
        await self._audit(actor, "automation.deleted", automation)

    async def _controlled(self, actor: Actor, automation_id: uuid.UUID, version: int) -> Automation:
        automation, view = await self.service.locked(actor, automation_id, version)
        if not view.may_control:
            raise Forbidden(code="automation.not_allowed")
        return automation

    async def _audit(self, actor: Actor, action: str, automation: Automation) -> None:
        details = {"state": automation.state.value, "version": automation.version}
        await record(self.session, actor, action, "automation", automation.id, details)
