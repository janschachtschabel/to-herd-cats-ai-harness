"""The SQL of event rules (plan M7 decisions 8 and 9), scoped by the event's
organisation."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Run
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationKind,
    AutomationState,
)
from app.modules.messaging.models import Conversation
from app.modules.tags.models import SubjectType, Tagging
from app.modules.tickets.models import WorkItem

TICK = timedelta(microseconds=1)


@dataclass(frozen=True, slots=True)
class Cause:
    """The run whose step caused an event: its chain's depth, its automation, and the
    objects its term was about (for an event rule's run)."""

    depth: int
    automation_id: uuid.UUID | None
    subjects: frozenset[uuid.UUID]


class EventRuleRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def rules_for(self, event_type: str, space_id: uuid.UUID) -> list[Automation]:
        """The active rules of `event_type` whose place is in the space, locked until
        the transaction ends (in a fixed order, so two events never deadlock)."""
        stmt = (
            select(Automation)
            .join(Conversation, Conversation.id == Automation.conversation_id)
            .where(
                Automation.org_id == self.org_id,
                Automation.kind == AutomationKind.EVENT,
                Automation.state == AutomationState.ACTIVE,
                Automation.event_type == event_type,
                Conversation.org_id == self.org_id,
                Conversation.space_id == space_id,
            )
            .order_by(Automation.id)
            .with_for_update(of=Automation)
            .execution_options(populate_existing=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def cause(self, run_id: uuid.UUID) -> Cause | None:
        run = await self.session.scalar(
            select(Run).where(Run.org_id == self.org_id, Run.id == run_id)
        )
        if run is None:
            return None
        subjects = (
            select(AutomationEvent.subject_id)
            .join(AutomationFiring, AutomationFiring.id == AutomationEvent.firing_id)
            .where(AutomationFiring.org_id == self.org_id, AutomationFiring.run_id == run_id)
        )
        found = frozenset((await self.session.scalars(subjects)).all())
        return Cause(run.chain_depth, run.automation_id, found)

    async def tagged(self, ticket_id: uuid.UUID, tag_id: uuid.UUID) -> bool:
        stmt = select(
            exists().where(
                Tagging.org_id == self.org_id,
                Tagging.subject_type == SubjectType.TICKET,
                Tagging.subject_id == ticket_id,
                Tagging.tag_id == tag_id,
            )
        )
        return bool(await self.session.scalar(stmt))

    async def ticket_kind(self, ticket_id: uuid.UUID) -> str | None:
        stmt = select(WorkItem.kind).where(WorkItem.org_id == self.org_id, WorkItem.id == ticket_id)
        return await self.session.scalar(stmt)

    async def take(
        self,
        rule: Automation,
        event_id: uuid.UUID,
        subject_id: uuid.UUID,
        ids: dict[str, Any],
        depth: int,
    ) -> bool:
        """The event, waiting with the rule; False: the rule had it already."""
        stmt = (
            insert(AutomationEvent)
            .values(
                org_id=self.org_id,
                automation_id=rule.id,
                event_id=event_id,
                subject_id=subject_id,
                ids=ids,
                depth=depth,
            )
            .on_conflict_do_nothing(index_elements=["automation_id", "event_id"])
            .returning(AutomationEvent.event_id)
        )
        return await self.session.scalar(stmt) is not None

    async def waiting(self, automation_id: uuid.UUID) -> list[AutomationEvent]:
        stmt = select(AutomationEvent).where(
            AutomationEvent.org_id == self.org_id,
            AutomationEvent.automation_id == automation_id,
            AutomationEvent.firing_id.is_(None),
        )
        return list((await self.session.scalars(stmt)).all())

    async def assign(
        self, automation_id: uuid.UUID, firing_id: uuid.UUID, only: uuid.UUID | None = None
    ) -> None:
        """The waiting events (or only the event `only`) were taken by the term."""
        stmt = update(AutomationEvent).where(
            AutomationEvent.org_id == self.org_id,
            AutomationEvent.automation_id == automation_id,
            AutomationEvent.firing_id.is_(None),
        )
        if only is not None:
            stmt = stmt.where(AutomationEvent.event_id == only)
        await self.session.execute(stmt.values(firing_id=firing_id))

    async def of_firing(self, firing_id: uuid.UUID) -> list[AutomationEvent]:
        stmt = (
            select(AutomationEvent)
            .where(AutomationEvent.org_id == self.org_id, AutomationEvent.firing_id == firing_id)
            .order_by(AutomationEvent.event_id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def free_term(self, automation_id: uuid.UUID, at: datetime) -> datetime:
        """`at`, or just after the rule's latest term if that is not earlier (a term is
        logged once: `uq_automation_firing_term`); the rule's row is locked."""
        stmt = select(func.max(AutomationFiring.due_at)).where(
            AutomationFiring.org_id == self.org_id,
            AutomationFiring.automation_id == automation_id,
        )
        latest = await self.session.scalar(stmt)
        return at if latest is None or latest < at else latest + TICK
