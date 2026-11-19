"""Separate database roles (plan M9 task 18, J14; ASVS 5.0 V13.2.2), an option: the
migration role (HERD_MIGRATE_DATABASE_URL) owns the schema and runs migrations,
backups and restores; the runtime role (HERD_DATABASE_RUNTIME_ROLE) gets data rights
only, on every table now and on those later migrations create. The default stays one
role.

The second role is made in the test database's cluster, which needs CREATEROLE (CI's
role is a superuser); without it that test is skipped and the grants are still run once,
to the test's own role, so their SQL is checked everywhere."""

import secrets
import uuid
from collections.abc import AsyncIterator

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.config import Settings, get_settings
from app.core.db import make_engine
from app.core.db_roles import grant_runtime_role, schema_owner_problem
from app.ops.pgtools import child_env

OWNER_URL = get_settings().test_database_url


async def _can_create_roles(conn: AsyncConnection) -> bool:
    row = (
        await conn.execute(
            text("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user")
        )
    ).scalar()
    return bool(row)


@pytest.fixture
async def runtime_role(engine: AsyncEngine) -> AsyncIterator[tuple[str, str]]:
    """A login role of its own (dropped afterwards), with the runtime grants."""
    owner = make_engine(OWNER_URL, isolation_level="AUTOCOMMIT")
    async with owner.connect() as conn:
        if not await _can_create_roles(conn):
            await owner.dispose()
            pytest.skip("the test database's role cannot create roles (CREATEROLE)")
        name, password = f"herd_rt_{uuid.uuid4().hex[:12]}", secrets.token_hex(16)
        await conn.execute(text(f"CREATE ROLE {name} LOGIN PASSWORD '{password}'"))
        try:
            await conn.run_sync(grant_runtime_role, name)
            yield name, password
        finally:
            await conn.execute(text("DROP TABLE IF EXISTS j14_made_later"))
            await conn.execute(text(f"DROP OWNED BY {name}"))
            await conn.execute(text(f"DROP ROLE {name}"))
    await owner.dispose()


async def _refused(conn: AsyncConnection, statement: str) -> None:
    with pytest.raises(DBAPIError) as raised:
        async with conn.begin_nested():
            await conn.execute(text(statement))
    assert "permission denied" in str(raised.value) or "must be owner" in str(raised.value)


async def test_the_runtime_role_cannot_alter_the_schema(runtime_role: tuple[str, str]) -> None:
    name, password = runtime_role
    url = make_url(OWNER_URL).set(username=name, password=password)
    runtime = make_engine(url)
    try:
        async with runtime.connect() as conn:
            # Data: read, write, number.
            await conn.execute(text("SELECT count(*) FROM app_user"))
            await conn.execute(
                text("INSERT INTO rate_limit_hit (id, key, hit_at) VALUES (:id, 'j14', now())"),
                {"id": uuid.uuid4()},
            )
            await conn.execute(text("DELETE FROM rate_limit_hit WHERE key = 'j14'"))
            await conn.commit()
            # Schema: nothing.
            for statement in (
                "ALTER TABLE app_user ADD COLUMN j14 int",
                "CREATE TABLE j14_own (x int)",
                "DROP TABLE rate_limit_hit",
                "CREATE INDEX j14_index ON app_user (id)",
                "TRUNCATE rate_limit_hit",
            ):
                await _refused(conn, statement)
            # Restoring needs the schema's owner: refused up front, by code.
            assert await schema_owner_problem(conn) == "restore.not_schema_owner"
        # A table a later migration makes (as the owner) is the runtime role's to use.
        owner = make_engine(OWNER_URL, isolation_level="AUTOCOMMIT")
        async with owner.connect() as conn:
            await conn.execute(text("CREATE TABLE j14_made_later (x int)"))
            assert await schema_owner_problem(conn) is None
        await owner.dispose()
        async with runtime.connect() as conn:
            await conn.execute(text("INSERT INTO j14_made_later VALUES (1)"))
            assert await conn.scalar(text("SELECT count(*) FROM j14_made_later")) == 1
            await _refused(conn, "ALTER TABLE j14_made_later ADD COLUMN y int")
    finally:
        await runtime.dispose()


async def test_the_grants_run_as_written(engine: AsyncEngine) -> None:
    """Their SQL, where no second role can be made: to the test's own role, undone."""
    async with engine.connect() as conn:
        role = await conn.scalar(text("SELECT current_user"))
        await conn.run_sync(grant_runtime_role, role)
        await conn.rollback()


def test_migrations_backups_and_restores_take_the_migration_role() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://herd_app@db:5432/herd",
        database_password=SecretStr("app-pw"),
        migrate_database_url="postgresql+asyncpg://herd_owner@db:5432/herd",
        migrate_database_password=SecretStr("owner-pw"),
        database_runtime_role="herd_app",
    )
    assert settings.database().username == "herd_app"
    migrate = settings.migrate_database()
    assert migrate.username == "herd_owner" and migrate.password == "owner-pw"
    env = child_env(settings)  # pg_dump, pg_restore, psql
    assert env["PGUSER"] == "herd_owner" and env["PGPASSWORD"] == "owner-pw"
    assert "owner-pw" not in repr(settings) and "owner-pw" not in str(migrate)
    one = Settings(database_url="postgresql+asyncpg://herd@db:5432/herd")
    assert one.migrate_database() == one.database()  # the default: one role


def test_the_runtime_role_must_be_a_plain_name() -> None:
    for bad in ("herd app", "herd;drop", "Herd", '"x"', "x" * 64):
        with pytest.raises(ValidationError, match="HERD_DATABASE_RUNTIME_ROLE"):
            Settings(database_runtime_role=bad)
    assert Settings(database_runtime_role="herd_app").database_runtime_role == "herd_app"
    with pytest.raises(ValidationError, match="needs HERD_DATABASE_RUNTIME_ROLE"):
        Settings(migrate_database_url="postgresql+asyncpg://herd_owner@db:5432/herd")


async def test_the_runtime_role_only_reads_the_recorded_revision(
    runtime_role: tuple[str, str],
) -> None:
    """`/ready` reads `alembic_version`; writing it is the migration role's alone, so
    code running as the app cannot make the next migration replay or skip revisions
    (review M9b Task 18, R18-8)."""
    name, password = runtime_role
    runtime = make_engine(make_url(OWNER_URL).set(username=name, password=password))
    try:
        async with runtime.connect() as conn:
            assert await conn.scalar(text("SELECT version_num FROM alembic_version"))
            for statement in (
                "UPDATE alembic_version SET version_num = 'r18_8'",
                "INSERT INTO alembic_version (version_num) VALUES ('r18_8')",
                "DELETE FROM alembic_version",
                "TRUNCATE alembic_version",
            ):
                await _refused(conn, statement)
    finally:
        await runtime.dispose()
