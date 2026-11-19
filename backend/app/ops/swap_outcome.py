"""Which state the database holds once a swap ended (review M9b F1 and F5), read from
the database itself, never assumed.

The swap (`swap.py`) drops and creates schema `public`, so the schema's oid changes in
its transaction; as its last statement before COMMIT it comments the new schema with a
token of this swap. Its psql session carries the token in `application_name`.

After the session ended (or was killed: then its backend is ended first, so a COMMIT
in flight has either happened or not):

- SWAPPED: the schema has this swap's comment: the swap's own COMMIT went through;
- KEPT: the schema has the oid it had before: rolled back, the old state is whole;
- BROKEN: neither: the dump's script ended the swap's transaction itself (a `COMMIT`
  in an object's definition) and the old schema is gone;
- UNKNOWN: the database could not be read, or the session did not end.

The comment is removed again after a swap (`clear_marker`); one left behind is
harmless (a restore leaves a comment on `public` out, `dump_toc.py`).
"""

import asyncio
from enum import StrEnum

from sqlalchemy import bindparam, text

from app.core.config import Settings
from app.core.db import make_engine

SETTLE_SECONDS = 30.0
_POLL_SECONDS = 0.2
_SCHEMA = text(
    "SELECT oid::bigint, pg_catalog.obj_description(oid, 'pg_namespace')"
    " FROM pg_catalog.pg_namespace WHERE nspname = 'public'"
)
_SESSIONS = text(
    "SELECT count(pg_catalog.pg_terminate_backend(pid, 1000)) FROM pg_catalog.pg_stat_activity"
    " WHERE application_name = :app AND pid <> pg_catalog.pg_backend_pid()"
).bindparams(bindparam("app"))


class Outcome(StrEnum):
    KEPT = "kept"
    SWAPPED = "swapped"
    BROKEN = "broken"
    UNKNOWN = "unknown"


def app_name(token: str) -> str:
    return f"herd-swap-{token}"


def marker(token: str) -> str:
    return f"herd-swap {token}"


async def schema_oid(settings: Settings) -> int:
    """The oid of schema `public` now (0 when there is none)."""
    engine = make_engine(settings.migrate_database(), settings=settings)
    try:
        async with engine.connect() as conn:
            row = (await conn.execute(_SCHEMA)).first()
            return int(row[0]) if row is not None else 0
    finally:
        await engine.dispose()


async def settle(settings: Settings, token: str, before: int) -> Outcome:
    """End the swap's session if it still runs, then read which state is there."""
    engine = make_engine(settings.migrate_database(), settings=settings)
    try:
        async with asyncio.timeout(SETTLE_SECONDS), engine.connect() as conn:
            while await conn.scalar(_SESSIONS, {"app": app_name(token)}):
                await conn.commit()
                await asyncio.sleep(_POLL_SECONDS)
            row = (await conn.execute(_SCHEMA)).first()
    except Exception:  # unreachable, or the session did not end: not known
        return Outcome.UNKNOWN
    finally:
        await engine.dispose()
    if row is not None and row[1] == marker(token):
        return Outcome.SWAPPED
    if row is not None and int(row[0]) == before:
        return Outcome.KEPT
    return Outcome.BROKEN


async def clear_marker(settings: Settings) -> None:
    """Remove the swap's comment (best effort: one left behind does no harm)."""
    engine = make_engine(settings.migrate_database(), settings=settings)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("COMMENT ON SCHEMA public IS NULL"))
    except Exception:  # noqa: S110 (a leftover comment is left out of every restore)
        pass
    finally:
        await engine.dispose()
