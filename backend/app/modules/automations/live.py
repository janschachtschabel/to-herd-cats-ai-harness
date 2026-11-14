"""Telling the people who see an automation that it changed (plan M7 task 7), so their
lists reload: ids only, never its words.

- `changed`: in the transaction of any change (made, changed, paused, resumed,
  deleted, run now, taken over, paused by the system): one outbox event
  `automation.updated` (the automation's id; its place's space as the event's space).
- `automation_live` (outbox handler, registered in `handlers.py`): one
  `automation.changed` per person who may see the automation now, by the rule of its
  routes (`sight.py`: its owner, its agent's responsible person, the managers of its
  place's space, `agent.manage`; nobody without `ai.use` or `agent.manage`), with
  the automation's id; `publish_live` sends it to that person's streams (with the
  space's id). A deleted automation is told too, so lists drop it. Idempotent enough:
  a second delivery makes a client reload once more.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, can
from app.core.outbox import Acting, Event, emit
from app.modules.agents.repository import AgentRepository
from app.modules.automations.manage_repository import ManageRepository
from app.modules.automations.models import Automation
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.sight import sight_of
from app.modules.automations.standing import person

CHANGED = "automation.updated"  # the change, for the worker
LIVE = "automation.changed"  # one per person who sees it, for their streams


async def changed(
    session: AsyncSession, automation: Automation, actor: Acting, space_id: uuid.UUID | None
) -> None:
    await emit(
        session,
        type=CHANGED,
        actor=actor,
        space_id=space_id,
        subject_type="automation",
        subject_id=automation.id,
        payload={"automation_id": str(automation.id)},
    )


async def automation_live(session: AsyncSession, event: Event) -> None:
    if event.type != CHANGED or event.subject_type != "automation":
        return
    automation = await AutomationRepository(session, event.org_id).get(event.subject_id)
    if automation is None:
        return
    agent = await AgentRepository(session, event.org_id).get(automation.agent_id)
    responsible = agent.responsible_user_id if agent is not None else None
    candidates = {automation.owner_user_id, *await ManageRepository(session, event.org_id).admins()}
    if responsible is not None:
        candidates.add(responsible)
    if event.space_id is not None:
        candidates |= set(
            await AutomationRepository(session, event.org_id).managers(event.space_id)
        )
    for user_id in sorted(candidates):
        if await _sees(session, event, automation, responsible, user_id):
            await emit(
                session,
                type=LIVE,
                actor=event.acting,
                space_id=event.space_id,
                subject_type="automation",
                subject_id=automation.id,
                payload={"user_id": str(user_id), "automation_id": str(automation.id)},
            )


async def _sees(
    session: AsyncSession,
    event: Event,
    automation: Automation,
    responsible: uuid.UUID | None,
    user_id: uuid.UUID,
) -> bool:
    actor = await person(session, event.org_id, user_id)
    if actor is None:
        return False
    sight = await sight_of(session, actor)
    if not sight.sees:
        return False
    if sight.manages_all or user_id in (automation.owner_user_id, responsible):
        return True
    space_id = event.space_id
    return space_id is not None and await can(session, actor, Action.SPACE_MANAGE, space_id)
