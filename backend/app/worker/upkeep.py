"""The due loop's expiry upkeep (plan M9 task 8): rows whose time has run out go once
the period of their rule in `app/core/retention.py` has passed (`Upkeep` with `by =
EXPIRY`): ended login sessions after an hour (live editing may still save for them),
OAuth and OIDC flows at their expiry, collab grants an hour after theirs, rate-limit
hits after the limiter's window, AI rate windows an hour after they began. The
modules still clear their own on the way (a login, a new flow, a new grant, a limit
check); the upkeep catches what nobody comes back for.

It also marks backups whose process died (`backup_run` rows still `running` while no
backup holds the backup lock, plan M9 task 8) `interrupted`, so a backup killed by its
job's time limit does not stay `running`.

`DueLoop.cleanup_if_due` runs it (`run_upkeep`), one transaction per batch and table.
The expiry is judged at the wall time (`wall`), the time the modules write and check
those columns against (a login is valid while `expires_at > utcnow()`), never at the
clock that schedules, which can run ahead of the wall time (the browser tests move it)
and would end logins still valid; the backups at the clock's `now`, which their runs
are written with (`app/ops`)."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.core.retention import EXPIRY, RETENTION, Upkeep
from app.models_registry import Base
from app.modules.backups.repository import BackupRunRepository
from app.worker.upkeep_repository import delete_older

EXPIRING: dict[str, Upkeep] = {
    table: rule
    for table, rule in RETENTION.items()
    if isinstance(rule, Upkeep) and rule.by == EXPIRY
}


async def remove_expired(session: AsyncSession, table: str, now: datetime, limit: int) -> int:
    """Up to `limit` rows of `table` past their period at `now`; how many."""
    rule = EXPIRING[table]
    target = Base.metadata.tables[table]
    return await delete_older(session, target, target.c[rule.since], now - rule.after, limit)


async def run_upkeep(database: Database, *, wall: datetime, now: datetime, limit: int) -> int:
    """Every expiring table at `wall`, batch by batch (one transaction each), then the
    dead backups at `now`; how many rows were removed."""
    removed = 0
    for table in EXPIRING:
        while True:
            async with database.session_factory() as session, session.begin():
                count = await remove_expired(session, table, wall, limit)
            removed += count
            if count < limit:
                break
    async with database.session_factory() as session, session.begin():
        await BackupRunRepository(session).interrupt_dead(now)
    return removed
