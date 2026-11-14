"""The SQL of automations.

Claiming a due automation is the worker's, across organisations (like claiming a
run; nothing of it is shown to anyone); everything after is scoped by the
automation's organisation.
"""

import uuid
from datetime import datetime

from sqlalchemy import exists, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.access_repository import person_holds_role
from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.agents.models import Run, RunState
from app.modules.automations.event_models import EventNote
from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationState,
    FiringOutcome,
    PausedReason,
)
from app.modules.groups.models import GroupMember
from app.modules.messaging.models import SYSTEM_AUTHOR, Conversation, ConversationKind, Message
from app.modules.spaces.models import SpaceMember
from app.modules.users.models import User


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


async def claim_failed(
    session: AsyncSession, automation_id: uuid.UUID, due_at: datetime
) -> Automation | None:
    """The automation whose term at `due_at` could not fire, locked, if it is still
    active and due then (None: another worker holds it, or it changed meanwhile)."""
    stmt = (
        select(Automation)
        .where(
            Automation.id == automation_id,
            Automation.state == AutomationState.ACTIVE,
            Automation.next_due_at == due_at,
        )
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    return await session.scalar(stmt)


class AutomationRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def get(self, automation_id: uuid.UUID, *, lock: bool = False) -> Automation | None:
        stmt = select(Automation).where(
            Automation.org_id == self.org_id, Automation.id == automation_id
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def place(self, automation: Automation) -> Conversation:
        stmt = select(Conversation).where(
            Conversation.org_id == self.org_id, Conversation.id == automation.conversation_id
        )
        return (await self.session.scalars(stmt)).one()  # the automation goes with it

    async def log(
        self,
        automation: Automation,
        due_at: datetime,
        fired_at: datetime,
        outcome: FiringOutcome,
        run_id: uuid.UUID | None = None,
        *,
        firing_id: uuid.UUID | None = None,
        event: EventNote | None = None,
    ) -> None:
        """The term's row in the log (a started run's with the instruction it was
        given and, for an event rule's, what it is told of the events); a second row
        for the same term fails the transaction (`uq_automation_firing_term`). A
        logged term ends a streak of terms that could not fire."""
        assert automation.org_id == self.org_id
        started = outcome == FiringOutcome.STARTED
        told = event if started else None
        automation.term_errors = 0
        self.session.add(
            AutomationFiring(
                id=firing_id or uuid7(),
                org_id=self.org_id,
                automation_id=automation.id,
                due_at=due_at,
                fired_at=fired_at,
                outcome=outcome,
                run_id=run_id,
                instruction=automation.instruction if started else None,
                event_type=told.type if told else None,
                event_count=told.count if told else None,
                event_objects=told.objects if told else None,
            )
        )
        await self.session.flush()

    async def open_run(self, automation_id: uuid.UUID) -> uuid.UUID | None:
        """The automation's run not yet done (its lane holds at most one)."""
        stmt = select(Run.id).where(
            Run.org_id == self.org_id,
            Run.automation_id == automation_id,
            Run.state != RunState.DONE,
        )
        return await self.session.scalar(stmt.limit(1))

    async def firing_of(self, run_id: uuid.UUID) -> AutomationFiring | None:
        """The term that started the run."""
        stmt = select(AutomationFiring).where(
            AutomationFiring.org_id == self.org_id, AutomationFiring.run_id == run_id
        )
        return await self.session.scalar(stmt)

    async def log_page(
        self, automation_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[AutomationFiring]:
        """The automation's log, newest term first (`before`: a row's id, the cursor)."""
        stmt = (
            select(AutomationFiring)
            .where(
                AutomationFiring.org_id == self.org_id,
                AutomationFiring.automation_id == automation_id,
            )
            .order_by(AutomationFiring.due_at.desc(), AutomationFiring.id.desc())
            .limit(limit)
        )
        if before is not None:
            cursor = select(AutomationFiring.due_at).where(
                AutomationFiring.org_id == self.org_id, AutomationFiring.id == before
            )
            stmt = stmt.where(
                tuple_(AutomationFiring.due_at, AutomationFiring.id)
                < tuple_(cursor.scalar_subquery(), literal(before))
            )
        return list((await self.session.scalars(stmt)).all())

    async def entry_of(self, firing_id: uuid.UUID) -> Message | None:
        """The term's system entry at its place, wherever it is (None: not posted)."""
        stmt = select(Message).where(
            Message.org_id == self.org_id,
            Message.author_type == SYSTEM_AUTHOR,
            Message.client_id == firing_id,
            Message.parent_id.is_(None),
        )
        return await self.session.scalar(stmt)

    async def thread_of(self, firing_id: uuid.UUID, *, lock: bool = False) -> Message | None:
        """The thread a term opened in a channel: its system entry, the root (None at
        any other place)."""
        stmt = (
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.org_id == self.org_id,
                Message.author_type == SYSTEM_AUTHOR,
                Message.client_id == firing_id,
                Message.parent_id.is_(None),
                Conversation.kind == ConversationKind.CHANNEL,
            )
        )
        if lock:
            stmt = stmt.with_for_update(of=Message).execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def pause(self, automation: Automation, reason: PausedReason) -> None:
        """Paused (locked by the caller); it keeps its next term."""
        automation.state = AutomationState.PAUSED
        automation.paused_reason = reason
        automation.version += 1
        await self.session.flush()

    async def managers(self, space_id: uuid.UUID) -> list[uuid.UUID]:
        """The active people who manage the space (`admin`) through a membership of
        their own or of a group. System admins without one are left out, as for a
        space's moderators (`proposals.repository`)."""
        direct = exists().where(
            SpaceMember.space_id == space_id,
            SpaceMember.member_type == PrincipalType.USER,
            SpaceMember.member_id == User.id,
            SpaceMember.role == SpaceRole.ADMIN,
        )
        through_group = exists().where(
            SpaceMember.space_id == space_id,
            SpaceMember.member_type == PrincipalType.GROUP,
            SpaceMember.role == SpaceRole.ADMIN,
            GroupMember.group_id == SpaceMember.member_id,
            GroupMember.member_type == PrincipalType.USER,
            GroupMember.member_id == User.id,
        )
        stmt = (
            select(User.id)
            .where(
                User.org_id == self.org_id,
                or_(direct, through_group),
                person_holds_role(literal(space_id), SpaceRole.ADMIN),
            )
            .order_by(User.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def advance(self, automation: Automation, next_due_at: datetime | None) -> None:
        """The automation's next term; none: it is done (a `once` that fired)."""
        assert automation.org_id == self.org_id
        automation.next_due_at = next_due_at
        if next_due_at is None:
            automation.state = AutomationState.DONE
        await self.session.flush()
