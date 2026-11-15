"""SQL of the due loop's expiry upkeep (`app/worker/upkeep.py`): installation-wide, like
the other retention deletes of the due loop, since a row past its period is no one's."""

from datetime import datetime

from sqlalchemy import Column, Table, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import locked_batch


async def delete_older(
    session: AsyncSession, table: Table, column: Column[datetime], cutoff: datetime, limit: int
) -> int:
    """Up to `limit` rows of `table` whose `column` lies before `cutoff`, of every
    organisation; rows another worker is deleting are skipped. How many."""
    (key,) = table.primary_key.columns.values()
    doomed = locked_batch(
        select(key).where(column < cutoff).limit(limit).with_for_update(skip_locked=True),
        f"doomed_{table.name}",
    )
    stmt = delete(table).where(key == doomed.c[key.name])
    return int((await session.execute(stmt)).rowcount)  # type: ignore[attr-defined]
