"""Audit entries that outlive a refused change (review M10 task 3b, R3b-5; review M10
task 1, R1-M2).

An admin's look into a foreign team or personal space (`space.admin_access`) and a
private calendar event read by admin power (`calendar.private_read`) happened even
when the change that followed is refused. The recorder writes them in the caller's
transaction and notes them here (`note`); when that transaction rolls back, `write`
writes the noted entries again in a transaction of their own, on a session of their
own (the caller's bind: in production its own connection), and forgets them. Both
entries are once per admin, target and UTC day, so writing one twice changes nothing.

Services never commit. The HTTP boundary (`core/db.get_session`) calls `write` after a
failed request's rollback (`core/db.after_rollback`); any other caller that rolls back
(an import, an agent's step) calls `write` itself, after its rollback: before it, the
caller's own uncommitted entry would hold the daily index and `write` would wait on it.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import after_rollback
from app.modules.audit.repository import AuditRepository

_KEPT = "herd.audit_kept"


def note(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Remembers entries (insert values) to write again should the caller's
    transaction roll back."""
    if not rows:
        return
    if after_rollback(session, write):  # a new transaction: what an earlier one noted is in
        session.info[_KEPT] = []
    session.info.setdefault(_KEPT, []).extend(rows)


async def write(session: AsyncSession) -> None:
    """Writes the noted entries in a transaction of their own and forgets them. Call it
    after the caller's transaction rolled back."""
    rows: list[dict[str, Any]] | None = session.info.pop(_KEPT, None)
    if not rows:
        return
    async with AsyncSession(bind=session.bind) as own, own.begin():
        await AuditRepository(own).add_many_unless_present(rows)
