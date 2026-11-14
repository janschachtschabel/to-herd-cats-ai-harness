"""The SQL of automations.

Claiming a due automation is the worker's, across organisations (like claiming a
run; nothing of it is shown to anyone); everything after is scoped by the
automation's organisation.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationState,
    FiringOutcome,
)


async def claim_due(session: AsyncSession, now: datetime) -> Automation | None:
    """The most overdue active automation due at `now`, locked until the caller's
    transaction ends; one another worker holds is passed over (`SKIP LOCKED`), and
    one it has fired meanwhile is no longer due when the lock is taken (the row is
    read again under the lock)."""
    stmt = (
        select(Automation)
        .where(Automation.state == AutomationState.ACTIVE, Automation.next_due_at <= now)
        .order_by(Automation.next_due_at, Automation.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    return await session.scalar(stmt)


class AutomationRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def log(
        self,
        automation: Automation,
        due_at: datetime,
        fired_at: datetime,
        outcome: FiringOutcome,
        run_id: uuid.UUID | None = None,
    ) -> None:
        """The term's row in the log; a second row for the same term fails the
        transaction (`uq_automation_firing_term`)."""
        assert automation.org_id == self.org_id
        self.session.add(
            AutomationFiring(
                org_id=self.org_id,
                automation_id=automation.id,
                due_at=due_at,
                fired_at=fired_at,
                outcome=outcome,
                run_id=run_id,
            )
        )
        await self.session.flush()

    async def advance(self, automation: Automation, next_due_at: datetime | None) -> None:
        """The automation's next term; none: it is done (a `once` that fired)."""
        assert automation.org_id == self.org_id
        automation.next_due_at = next_due_at
        if next_due_at is None:
            automation.state = AutomationState.DONE
        await self.session.flush()
