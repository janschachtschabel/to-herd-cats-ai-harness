"""Pausing an automation by itself (plan M7 decisions 2 and 13), with an activity
entry (reason `automation`, bound to the automation, ids only in its event):

- `owner`: its owner no longer may run it (`standing.owner_may_run`): the agent's
  responsible person learns of it, and at a place in a space also the people who
  manage the space (in a DM, only the responsible person: nobody else sees it). One
  of them, or anyone who could make it, may take it over (`takeover.py`).
- `failing`: three runs in a row did not end `completed`: its owner learns of it.

Called in the transaction that found it out (the due loop's, a run's end), with the
automation's row locked.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventActor, emit
from app.core.principal import Principal
from app.modules.agents.repository import AgentRepository
from app.modules.automations.models import Automation, PausedReason
from app.modules.automations.repository import AutomationRepository
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository


async def pause(session: AsyncSession, automation: Automation, reason: PausedReason) -> None:
    repo = AutomationRepository(session, automation.org_id)
    await repo.pause(automation, reason)
    told = await _told(session, repo, automation, reason)
    rows = [(user_id, NotificationReason.AUTOMATION) for user_id in sorted(told)]
    notes = NotificationRepository(session, automation.org_id)
    for notification in await notes.add_for_automation(automation.id, rows):
        await emit(
            session,
            type="notification.created",
            actor=EventActor(automation.org_id, Principal.agent(automation.agent_id)),
            space_id=None,
            subject_type="notification",
            subject_id=notification.id,
            payload={
                "notification_id": str(notification.id),
                "conversation_id": None,
                "message_id": None,
                "user_id": str(notification.user_id),
            },
        )


async def _told(
    session: AsyncSession,
    repo: AutomationRepository,
    automation: Automation,
    reason: PausedReason,
) -> set[uuid.UUID]:
    if reason == PausedReason.FAILING:
        return {automation.owner_user_id}
    agent = await AgentRepository(session, automation.org_id).get(automation.agent_id)
    told = {agent.responsible_user_id} if agent is not None else set()
    place = await repo.place(automation)
    if place.space_id is not None:
        told |= set(await repo.managers(place.space_id))
    return told
