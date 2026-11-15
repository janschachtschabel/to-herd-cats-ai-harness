"""Taking an automation over (plan M7 decision 2): a person who could make it
themselves (`standing.may_own`: `ai.use`, the agent within reach, writing at its
place, and for an event rule managing its space) becomes its owner; it runs on with
their rights and their name, and a paused one resumes (its next term, if past, fires
once). Rights never move without this explicit step. The route comes with the
management API (task 7). The previous owner's open run, if any, is asked to stop
(`agents.control.request_cancel`, by the taker, in the same transaction): it would
hold the automation's lane, perhaps waiting for a release nobody gives.

- Someone without `ai.use` sees no automations: 404 `automation.not_found`, as for
  an unknown id.
- A stale `version`: 409 `automation.version_conflict` (with `current_version`).
- Someone who may not own it: 403 `automation.not_allowed`.
- Someone at the cap of open automations: 409 `automation.limit` (`hold_room`).

Audited (`automation.taken_over`, ids only); its watchers hear of it
(`live.changed`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import Conflict, Forbidden, NotFound
from app.modules.agents.control import request_cancel
from app.modules.agents.repository import AgentRepository
from app.modules.audit.recorder import record
from app.modules.automations import live
from app.modules.automations.models import Automation, AutomationState
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.service import hold_room
from app.modules.automations.standing import may_own


async def take_over(
    session: AsyncSession, actor: Actor, automation_id: uuid.UUID, version: int
) -> Automation:
    repo = AutomationRepository(session, actor.org_id)
    automation = await repo.get(automation_id, lock=True)
    if automation is None or not await can(session, actor, Action.AI_USE):
        raise NotFound(code="automation.not_found")
    if automation.version != version:
        raise Conflict(
            code="automation.version_conflict",
            details={"current_version": automation.version},
        )
    agent = await AgentRepository(session, actor.org_id).get(automation.agent_id)
    assert agent is not None  # the automation goes with its agent
    place = await repo.place(automation)
    if not await may_own(session, actor, agent, place, automation.kind):
        raise Forbidden(code="automation.not_allowed")
    if automation.owner_user_id != actor.principal.id:
        await hold_room(session, actor.org_id, actor.principal.id)
    before = automation.owner_user_id
    automation.owner_user_id = actor.principal.id
    if automation.state == AutomationState.PAUSED:
        automation.state = AutomationState.ACTIVE
        automation.paused_reason = None
    automation.failures = 0
    automation.version += 1
    await session.flush()
    running = await repo.open_run(automation.id)
    if running is not None:
        await request_cancel(session, actor.org_id, running, actor.principal.id)
    details = {"from": str(before), "to": str(actor.principal.id)}
    await record(session, actor, "automation.taken_over", "automation", automation.id, details)
    await live.changed(session, automation, actor, place.space_id)
    return automation
