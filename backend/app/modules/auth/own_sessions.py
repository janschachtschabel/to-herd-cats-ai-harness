"""A person's own login sessions (ASVS 5.0 V7.5.2, J8): she lists the running ones and
ends one, or every one but the session she acts with. A session that is not hers, or
no longer runs, answers exactly like an unknown id. Ending is audited
(`user.session_ended`) with the session's id or the count, never the device."""

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.config import Settings
from app.core.errors import NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.audit.recorder import record
from app.modules.auth.models import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.auth.timing import session_clock

ENDED = "user.session_ended"


class OwnSessions:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        idle = settings.session_idle_hours
        self.sessions = SessionRepository(session, timedelta(hours=idle) if idle else None)

    async def list(self, actor: Actor, params: PageParams) -> Page[UserSession]:
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.sessions.list_running(
            actor.org_id,
            actor.principal.id,
            session_clock().now(),
            before=before,
            limit=params.limit + 1,
        )
        return id_page(list(rows), params.limit, lambda row: row.id)

    async def end(self, actor: Actor, session_id: uuid.UUID) -> None:
        """Her running session `session_id` ends; its row goes, so live streams and an
        open live editor of it end too."""
        now = session_clock().now()
        if not await self.sessions.delete_own(actor.org_id, actor.principal.id, session_id, now):
            raise NotFound(code="auth.session_not_found")
        await record(
            self.session, actor, ENDED, "user", actor.principal.id, {"session_id": str(session_id)}
        )

    async def end_others(self, actor: Actor, current: uuid.UUID) -> None:
        """Every session of hers but `current` ends, and her sign-ins waiting for the
        second factor."""
        count = await self.sessions.delete_for_user(actor.org_id, actor.principal.id, keep=current)
        if count:
            await record(self.session, actor, ENDED, "user", actor.principal.id, {"others": count})
