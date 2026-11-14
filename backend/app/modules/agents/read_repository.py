"""The SQL of what a run reads besides its tools (`executor.py`): the conversation it
answers, and where what it has read is now and that place's current policy (spec
7.3), in the run's organisation."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor, visible_space_ids
from app.modules.agents.models import Run
from app.modules.ai.policy import Policy
from app.modules.messaging.models import Message, MessageKind
from app.modules.spaces.models import Space
from app.modules.tickets.models import WorkItem
from app.modules.wiki.models import Page

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
    by_agent: bool
    text: str


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
            select(Message.kind, Message.body_md, at)
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
        rows.sort(
            key=lambda row: row[2] or until
        )  # stable: messages of one moment keep their order
        return [Said(kind == MessageKind.AGENT, body) for kind, body, _ in rows]

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

    async def still_visible(self, actor: Actor, space_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Which of the spaces the actor (with its read scope) may read now."""
        stmt = visible_space_ids(actor).where(Space.id.in_(sorted(space_ids)))
        return set(await self.session.scalars(stmt))
