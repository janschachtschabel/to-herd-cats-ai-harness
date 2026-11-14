"""The activity view, tab "Für mich" (spec 6.2): a person's notifications, newest
first, each with its conversation, author and the start of the message.

Only one's own notifications exist for one (someone else's id is 404
`notification.not_found`, as is one whose conversation one no longer sees). Marking
read or done is idempotent; a change is emitted as `activity.changed` (the person's
id only), so the person's other tabs can refresh.
"""

import builtins
import dataclasses
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import NotFound
from app.core.outbox import emit
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import PrincipalType
from app.modules.messaging.activity_repository import ActivityEntry, ActivityRepository
from app.modules.messaging.agent_hooks import agent_hooks
from app.modules.messaging.visibility import ConversationReader
from app.modules.skills.sight import sight_of


@dataclass(frozen=True, slots=True)
class ActivityCount:
    open: int  # not done
    unread: int  # not done and not read


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = ConversationReader(session)

    async def _repo(self, actor: Actor) -> ActivityRepository:
        skills = await sight_of(self.session, actor)
        return ActivityRepository(self.session, self.reader.scope(actor), skills)

    async def list(
        self, actor: Actor, params: PageParams, only_open: bool = True
    ) -> Page[ActivityEntry]:
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await (await self._repo(actor)).page(before, params.limit + 1, only_open=only_open)
        return id_page(await self._named(actor, rows), params.limit, lambda e: e.notification.id)

    async def _named(
        self, actor: Actor, rows: Sequence[ActivityEntry]
    ) -> builtins.list[ActivityEntry]:
        """Agents as authors (an agent's message, timeline entry or proposal, plan M6):
        a person's name comes with the row; an author id that names no person is
        looked up among the agents."""
        ids = {
            e.author_id
            for e in rows
            if e.author_id is not None
            and e.author_name is None
            and e.author_type in (None, PrincipalType.AGENT)
        }
        if not ids:
            return list(rows)
        names = await agent_hooks().names(self.session, actor.org_id, ids)
        return [
            dataclasses.replace(e, author_name=names[e.author_id], author_type=PrincipalType.AGENT)
            if e.author_id in names and e.author_name is None
            else e
            for e in rows
        ]

    async def count_open(self, actor: Actor) -> ActivityCount:
        open_, unread = await (await self._repo(actor)).counts()
        return ActivityCount(open_, unread)

    async def mark_read(self, actor: Actor, notification_id: uuid.UUID) -> None:
        await self._mark(actor, notification_id, done=False)

    async def mark_done(self, actor: Actor, notification_id: uuid.UUID) -> None:
        await self._mark(actor, notification_id, done=True)

    async def read_all(self, actor: Actor) -> None:
        if await (await self._repo(actor)).mark(None, done=False):
            await self._changed(actor)

    async def _mark(self, actor: Actor, notification_id: uuid.UUID, *, done: bool) -> None:
        repo = await self._repo(actor)
        if not await repo.exists(notification_id):
            raise NotFound(code="notification.not_found")
        if await repo.mark(notification_id, done=done):
            await self._changed(actor)

    async def _changed(self, actor: Actor) -> None:
        await emit(
            self.session,
            type="activity.changed",
            actor=actor,
            space_id=None,
            subject_type="user",
            subject_id=actor.principal.id,
            payload={"user_id": str(actor.principal.id)},
        )
