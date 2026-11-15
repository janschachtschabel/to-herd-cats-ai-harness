"""Planner settings for tests that must hold whatever plan Postgres picks."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NESTED_LOOP_ONLY = (
    "enable_hashjoin",
    "enable_mergejoin",
    "enable_material",
    "enable_memoize",
    "enable_sort",
    "enable_hashagg",
)


async def force_nested_loops(session: AsyncSession) -> None:
    """Until the transaction ends: joins only as plain nested loops, so a subquery on
    the inner side is run again per outer row (as the planner may choose by itself
    with other statistics). `DELETE … WHERE id IN (SELECT … LIMIT n FOR UPDATE SKIP
    LOCKED)` then locks and deletes more than n rows."""
    for setting in NESTED_LOOP_ONLY:
        await session.execute(text(f"SET LOCAL {setting} = off"))
