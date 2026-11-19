"""Review M9b final, finding F2-6: `restore.not_schema_owner` asked for CREATE on schema
`public` and ownership of every table, but the swap needs ownership of the schema
(`DROP SCHEMA public`). A role that was granted CREATE on `public`, owns the tables it
made, and owns neither the schema nor the database passed the check and "Prüfen"; the
replace then took a safety archive, turned maintenance on and failed in the swap.

Ruling: the check requires ownership of the schema (or membership in its owner, which
the database's owner has for `pg_database_owner`)."""

import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.db import make_engine
from app.core.db_roles import schema_owner_problem
from tests.factories_restore import Target


@asynccontextmanager
async def _role(target: Target, *grants: str) -> AsyncIterator[AsyncConnection]:
    """A login role of its own in the target database (dropped afterwards), with
    `grants` run there as the test's role first; yields its connection."""
    admin = make_engine(target.settings.database(), isolation_level="AUTOCOMMIT")
    name, password = f"herd_f26_{uuid.uuid4().hex[:12]}", secrets.token_hex(16)
    async with admin.connect() as conn:
        allowed = await conn.scalar(
            text("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user")
        )
        if not allowed:
            await admin.dispose()
            pytest.skip("the test database's role cannot create roles (CREATEROLE)")
        await conn.execute(text(f"CREATE ROLE {name} LOGIN PASSWORD '{password}'"))
        own = make_engine(target.settings.database().set(username=name, password=password))
        try:
            for grant in grants:
                await conn.execute(text(grant.format(role=name)))
            async with own.connect() as mine:
                yield mine
        finally:
            await own.dispose()
            await conn.execute(text(f'ALTER DATABASE "{target.name}" OWNER TO current_user'))
            await conn.execute(text("ALTER SCHEMA public OWNER TO pg_database_owner"))
            await conn.execute(text(f"DROP OWNED BY {name}"))
            await conn.execute(text(f"DROP ROLE {name}"))
    await admin.dispose()


async def test_create_on_public_without_owning_it_cannot_restore(target: Target) -> None:
    async with _role(target, "GRANT CREATE ON SCHEMA public TO {role}") as conn:
        await conn.execute(text("CREATE TABLE f26_own (x int)"))  # owns every table
        await conn.commit()
        assert await schema_owner_problem(conn) == "restore.not_schema_owner"
        with pytest.raises(DBAPIError, match="must be owner of schema public"):
            await conn.execute(text("DROP SCHEMA public CASCADE"))


async def test_the_owner_of_the_database_or_of_the_schema_can_restore(target: Target) -> None:
    database = f'ALTER DATABASE "{target.name}" OWNER TO {{role}}'
    async with _role(target, database) as conn:
        assert await schema_owner_problem(conn) is None
    async with _role(target, "ALTER SCHEMA public OWNER TO {role}") as conn:
        assert await schema_owner_problem(conn) is None
