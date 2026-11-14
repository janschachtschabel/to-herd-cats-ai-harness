"""The SQL of the management API of automations (plan M7 decisions 12 and 14), scoped
by the caller's organisation and filtered by who may see an automation
(`sight.seen`, in SQL with the agent's responsible person and the place's space).

A row comes with what the API shows beside it: its agent's and its owner's name, its
place (kind, space, a channel's name, a ticket's number) and its latest term with the
run it started (one lateral look-up).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.permissions import ADMIN_ROLES
from app.core.repository import advisory_xact_lock
from app.modules.agents.models import Agent, Run
from app.modules.automations.models import Automation, AutomationFiring, AutomationState
from app.modules.automations.sight import AutomationSight, seen
from app.modules.messaging.models import Conversation
from app.modules.tags.models import Tag
from app.modules.tickets.models import WorkItem
from app.modules.users.models import User

# States that count toward the cap (a done `once` and a deleted automation do not).
OPEN_STATES = (AutomationState.ACTIVE, AutomationState.PAUSED)


@dataclass(frozen=True, slots=True)
class Row:
    automation: Automation
    agent_name: str | None
    owner_name: str | None
    place: Conversation
    responsible_id: uuid.UUID | None
    ticket_number: int | None
    last: AutomationFiring | None
    run: Run | None


class ManageRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def hold_owner(self, owner_id: uuid.UUID) -> int:
        """The owner's automations that count toward the cap; held until the
        transaction ends, so two creations do not both take the last place."""
        await advisory_xact_lock(self.session, f"automation.owner:{owner_id}")
        stmt = select(func.count()).where(
            Automation.org_id == self.org_id,
            Automation.owner_user_id == owner_id,
            Automation.state.in_(OPEN_STATES),
        )
        return int(await self.session.scalar(stmt) or 0)

    async def admins(self) -> list[uuid.UUID]:
        """The active owners and admins of the organisation (`agent.manage`)."""
        stmt = select(User.id).where(
            User.org_id == self.org_id,
            User.is_active.is_(True),
            User.system_role.in_(ADMIN_ROLES),
        )
        return list((await self.session.scalars(stmt)).all())

    async def tag_fits(self, tag_id: uuid.UUID, space_id: uuid.UUID) -> bool:
        """A system tag, or a tag of the space."""
        stmt = select(Tag.id).where(
            Tag.org_id == self.org_id,
            Tag.id == tag_id,
            or_(Tag.space_id.is_(None), Tag.space_id == space_id),
        )
        return await self.session.scalar(stmt) is not None

    async def one(self, sight: AutomationSight, automation_id: uuid.UUID) -> Row | None:
        rows = await self._rows(self._seen(sight).where(Automation.id == automation_id), 1)
        return rows[0] if rows else None

    async def page(
        self,
        sight: AutomationSight,
        where: ColumnElement[bool],
        before: uuid.UUID | None,
        limit: int,
    ) -> list[Row]:
        """Newest first (`before`: the cursor, an automation's id)."""
        stmt = self._seen(sight).where(where)
        if before is not None:
            stmt = stmt.where(Automation.id < before)
        return await self._rows(stmt.order_by(Automation.id.desc()), limit)

    def _seen(self, sight: AutomationSight) -> Select[Automation, Agent, Conversation]:
        return (
            select(Automation, Agent, Conversation)
            .join(Agent, Agent.id == Automation.agent_id)
            .join(Conversation, Conversation.id == Automation.conversation_id)
            .where(
                Automation.org_id == self.org_id,
                Automation.state != AutomationState.DELETED,
                seen(
                    sight,
                    Automation.owner_user_id,
                    Agent.responsible_user_id,
                    Conversation.space_id,
                ),
            )
        )

    async def _rows(self, stmt: Select[Automation, Agent, Conversation], limit: int) -> list[Row]:
        firing = aliased(AutomationFiring)
        last = (
            select(firing)
            .where(firing.org_id == self.org_id, firing.automation_id == Automation.id)
            .order_by(firing.due_at.desc(), firing.id.desc())
            .limit(1)
            .lateral("last_firing")
        )
        last_firing = aliased(AutomationFiring, last)
        owner = aliased(User)
        full = (
            stmt.add_columns(owner.name, WorkItem.number, last_firing, Run)
            .outerjoin(owner, owner.id == Automation.owner_user_id)
            .outerjoin(
                WorkItem,
                and_(WorkItem.org_id == self.org_id, WorkItem.id == Conversation.work_item_id),
            )
            .outerjoin(last, true())
            .outerjoin(Run, and_(Run.org_id == self.org_id, Run.id == last_firing.run_id))
            .limit(limit)
        )
        return [
            Row(
                automation=row[0],
                agent_name=row[1].name,
                owner_name=row[3],
                place=row[2],
                responsible_id=row[1].responsible_user_id,
                ticket_number=row[4],
                last=row[5],
                run=row[6],
            )
            for row in (await self.session.execute(full)).all()
        ]
