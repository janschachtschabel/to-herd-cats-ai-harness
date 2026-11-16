"""The schema lock for a whole restore (`core/migrations.SCHEMA_LOCK`): held on one
connection at session level from the first check to the last step, so no migration
(which takes it per transaction) runs in between, and no second restore. With `wait`
false (a replace an owner started, plan M9 task 13) a lock held elsewhere is
`SchemaLockBusy` at once instead of a wait."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.migrations import SCHEMA_LOCK


class SchemaLockBusy(Exception):  # noqa: N818 (a state of the installation)
    """Another restore or a migration holds the schema lock."""


@asynccontextmanager
async def schema_lock(conn: AsyncConnection, *, wait: bool = True) -> AsyncIterator[None]:
    params = {"name": SCHEMA_LOCK}
    if wait:
        await conn.execute(text("SELECT pg_advisory_lock(hashtextextended(:name, 0))"), params)
    else:
        taken = await conn.scalar(
            text("SELECT pg_try_advisory_lock(hashtextextended(:name, 0))"), params
        )
        if not taken:
            await conn.commit()
            raise SchemaLockBusy()
    await conn.commit()  # the lock is the session's; no transaction stays open
    try:
        yield
    finally:
        await conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:name, 0))"), params)
        await conn.commit()
