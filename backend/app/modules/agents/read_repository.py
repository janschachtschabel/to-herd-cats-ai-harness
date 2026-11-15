"""The SQL of what a run reads besides its tools (`executor.py`, `place.py`): the
conversation, the thread or the ticket it answers, and where what it has read is now
and that place's current policy (spec 7.3), in the run's organisation."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor, visible_space_ids
from app.core.principal import PrincipalType
from app.modules.agents.models import Agent
from app.modules.agents.run_models import Run
from app.modules.ai.policy import Policy
from app.modules.messaging.models import Conversation, ConversationKind, Message, MessageKind
from app.modules.spaces.models import Space
from app.modules.tickets.models import WorkItem
from app.modules.users.models import User
from app.modules.wiki.models import Page, PageStatus

HISTORY_MESSAGES = 200  # the newest top-level messages read; `context.window` cuts by chars


class ReadIds(Protocol):
    @property
    def pages(self) -> set[uuid.UUID]: ...
    @property
    def tickets(self) -> set[uuid.UUID]: ...


@dataclass(frozen=True, slots=True)
class Whereabouts:
    spaces: set[uuid.UUID]
    blocked: bool


@dataclass(frozen=True, slots=True)
class Said:
    """A message as a run reads it: whether an agent wrote it, its author (id and name
    as they are now; None once gone), its text, and whether it is marked personal."""

    by_agent: bool
    text: str
    author_id: uuid.UUID | None = None
    author_name: str | None = None
    message_id: uuid.UUID | None = None
    personal: bool = False


class ReadRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def said(self, conversation_id: uuid.UUID, until: datetime) -> list[Said]:
        """The conversation as a run answers it: the person's and the agent's top-level
        messages written up to `until` (the run's start), oldest first. An answer counts
        from the start of the run that wrote it, so a message the person sent while
        that run worked comes after it. Timeline notices (a run's stop) are left out."""
        answered = (
            select(Run.started_at)
            .where(Run.org_id == self.org_id, Run.id == Message.client_id)
            .scalar_subquery()
        )
        at = func.coalesce(answered, Message.created_at)
        stmt = (
            select(
                Message.kind,
                Message.body_md,
                Message.author_id,
                self._author_name(),
                Message.id,
                Message.personal,
                at,
            )
            .where(
                Message.org_id == self.org_id,
                Message.conversation_id == conversation_id,
                Message.parent_id.is_(None),
                Message.deleted_at.is_(None),
                Message.kind.in_((MessageKind.HUMAN, MessageKind.AGENT)),
                Message.created_at <= until,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(HISTORY_MESSAGES)
        )
        rows = list(reversed((await self.session.execute(stmt)).all()))
        rows.sort(key=lambda row: row[6] or until)  # stable: one moment keeps its order
        return [
            Said(k == MessageKind.AGENT, body, by, name, mid, marked)
            for k, body, by, name, mid, marked, _ in rows
        ]

    async def thread_root(self, trigger_id: uuid.UUID, *, lock: bool = False) -> Message | None:
        """The thread a mention's run answers in: the root of the mentioning message's
        thread (the message itself at the top level); None in a DM."""
        trigger = select(func.coalesce(Message.parent_id, Message.id)).where(
            Message.org_id == self.org_id, Message.id == trigger_id
        )
        stmt = (
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.org_id == self.org_id,
                Message.id == trigger.scalar_subquery(),
                Conversation.kind != ConversationKind.DM,
            )
        )
        if lock:
            stmt = stmt.with_for_update(of=Message).execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def thread(self, root_id: uuid.UUID, until: datetime) -> list[Said]:
        """A thread as a mention's run answers it: the people's and the agents' messages
        in it written up to `until` (the run's start), oldest first."""
        stmt = (
            select(
                Message.kind,
                Message.body_md,
                Message.author_id,
                self._author_name(),
                Message.id,
                Message.personal,
            )
            .where(
                Message.org_id == self.org_id,
                or_(Message.id == root_id, Message.parent_id == root_id),
                Message.deleted_at.is_(None),
                Message.kind.in_((MessageKind.HUMAN, MessageKind.AGENT)),
                Message.created_at <= until,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(HISTORY_MESSAGES)
        )
        rows = reversed((await self.session.execute(stmt)).all())
        return [
            Said(k == MessageKind.AGENT, body, by, name, mid, marked)
            for k, body, by, name, mid, marked in rows
        ]

    async def person_name(self, user_id: uuid.UUID) -> str | None:
        stmt = select(User.name).where(User.org_id == self.org_id, User.id == user_id)
        return await self.session.scalar(stmt)

    def _author_name(self) -> ColumnElement[str | None]:
        """The (correlated) message's author's name: a person's or an agent's."""
        person = select(User.name).where(
            Message.author_type == PrincipalType.USER,
            User.org_id == self.org_id,
            User.id == Message.author_id,
        )
        agent = select(Agent.name).where(
            Message.author_type == PrincipalType.AGENT,
            Agent.org_id == self.org_id,
            Agent.id == Message.author_id,
        )
        return func.coalesce(person.scalar_subquery(), agent.scalar_subquery())

    async def present(self, message_id: uuid.UUID) -> bool:
        """Whether the message is there and not deleted."""
        stmt = select(Message.id).where(
            Message.org_id == self.org_id, Message.id == message_id, Message.deleted_at.is_(None)
        )
        return await self.session.scalar(stmt) is not None

    async def ticket_number(self, work_item_id: uuid.UUID) -> int | None:
        stmt = select(WorkItem.number).where(
            WorkItem.org_id == self.org_id, WorkItem.id == work_item_id
        )
        return await self.session.scalar(stmt)

    async def policies(self, space_ids: set[uuid.UUID]) -> list[Policy]:
        """The spaces' policies as they are now."""
        if not space_ids:
            return []
        stmt = select(Space.ai_policy, Space.allowed_locations).where(
            Space.org_id == self.org_id, Space.id.in_(sorted(space_ids))
        )
        return [Policy.of(kind, allowed) for kind, allowed in await self.session.execute(stmt)]

    async def now(self, reads: ReadIds) -> Whereabouts:
        """Where the pages and tickets a run read are now. A page trashed, deleted or
        locked for AI (`no_ai`) since, or a ticket deleted, makes it `blocked`."""
        spaces: set[uuid.UUID] = set()
        found = 0
        blocked = False
        if reads.pages:
            pages = select(Page.space_id, Page.no_ai, Page.trashed_at).where(
                Page.org_id == self.org_id, Page.id.in_(sorted(reads.pages))
            )
            for space_id, no_ai, trashed_at in await self.session.execute(pages):
                spaces.add(space_id)
                found += 1
                blocked |= no_ai or trashed_at is not None
        if reads.tickets:
            tickets = select(WorkItem.space_id).where(
                WorkItem.org_id == self.org_id, WorkItem.id.in_(sorted(reads.tickets))
            )
            for space_id in await self.session.scalars(tickets):
                spaces.add(space_id)
                found += 1
        blocked |= found < len(reads.pages) + len(reads.tickets)
        return Whereabouts(spaces, blocked)

    async def draft_spaces(self, page_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """The spaces of those pages that are drafts now."""
        if not page_ids:
            return set()
        stmt = select(Page.space_id).where(
            Page.org_id == self.org_id,
            Page.id.in_(sorted(page_ids)),
            Page.status == PageStatus.DRAFT,
        )
        return set(await self.session.scalars(stmt))

    async def still_visible(self, actor: Actor, space_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Which of the spaces the actor (with its read scope) may read now."""
        stmt = visible_space_ids(actor).where(Space.id.in_(sorted(space_ids)))
        return set(await self.session.scalars(stmt))
