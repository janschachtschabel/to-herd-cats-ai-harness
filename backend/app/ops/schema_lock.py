"""The schema lock for a whole restore (`core/migrations.SCHEMA_LOCK`): held on one
connection at session level from the first check to the last step, so no migration
(which takes it per transaction) runs in between, and no second restore."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.migrations import SCHEMA_LOCK


@asynccontextmanager
async def schema_lock(conn: AsyncConnection) -> AsyncIterator[None]:
    params = {"name": SCHEMA_LOCK}
    await conn.execute(text("SELECT pg_advisory_lock(hashtextextended(:name, 0))"), params)
    await conn.commit()  # the lock is the session's; no transaction stays open
    try:
        yield
    finally:
        await conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:name, 0))"), params)
        await conn.commit()
