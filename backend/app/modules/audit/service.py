"""Reading the audit log (writing: `recorder`)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.audit.repository import AuditRepository, NamedEntry
from app.modules.audit.schemas import AuditQuery


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.entries = AuditRepository(session)

    async def list(self, actor: Actor, query: AuditQuery) -> Page[NamedEntry]:
        """The organisation's entries, newest first."""
        await require(self.session, actor, Action.AUDIT_READ)
        before = decode_cursor(query.cursor) if query.cursor else None
        rows = await self.entries.page(
            actor.org_id,
            actor_id=query.actor_id,
            action=query.action,
            before=before,
            limit=query.limit + 1,
        )
        items, more = rows[: query.limit], len(rows) > query.limit
        last = items[-1].entry if more else None
        return Page[NamedEntry](
            items=items, next_cursor=encode_cursor(last.created_at, last.id) if last else None
        )
