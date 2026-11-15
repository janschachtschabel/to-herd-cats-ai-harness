"""The due loop's expiry upkeep (plan M9 task 8): rows whose time has run out go once
the period of their rule in `app/core/retention.py` has passed (`Upkeep` with `by =
EXPIRY`): ended login sessions after an hour (live editing may still save for them),
OAuth and OIDC flows at their expiry, collab grants an hour after theirs, rate-limit
hits after the limiter's window, AI rate windows an hour after they began. The
modules still clear their own on the way (a login, a new flow, a new grant, a limit
check); the upkeep catches what nobody comes back for.

`DueLoop.cleanup_if_due` runs it, one transaction per batch and table."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retention import EXPIRY, RETENTION, Upkeep
from app.models_registry import Base
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
