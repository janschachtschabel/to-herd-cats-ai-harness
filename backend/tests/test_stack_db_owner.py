"""`python -m app.stack db-owner` (review M9b final, F2-1): the shipped stacks run the app
with a role that owns the database and its schema `public` and is no superuser.

Run as the bundled PostgreSQL's superuser before the app on every start: it makes the
role once (or takes it back from any attribute beyond LOGIN), sets its password from a
file it writes once, and hands the database, the schema and every object in it to the
role. An installation that ran as the superuser moves on its next start, no step by
hand. Here against a scratch database of the test cluster (needs CREATEROLE)."""

import io
import stat
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from app.core.listen import asyncpg_dsn
from app.stack.db_owner import OwnerSetup, run_db_owner
from tests.factories_restore import Target


@pytest.fixture
async def admin(target: Target) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(asyncpg_dsn(target.settings.database()))
    allowed = await connection.fetchval(
        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    )
    if not allowed:
        await connection.close()
        pytest.skip("db-owner runs as a superuser; the test database's role is none")
    yield connection
    await connection.close()


@pytest.fixture
async def owner(admin: asyncpg.Connection, target: Target) -> AsyncIterator[str]:
    name = f"herd_owner_{uuid.uuid4().hex[:10]}"
    yield name
    await admin.execute(f'ALTER DATABASE "{target.name}" OWNER TO current_user')
    if await admin.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", name):
        await admin.execute(f"DROP OWNED BY {name}")
        await admin.execute(f"DROP ROLE {name}")


def _setup(target: Target, owner: str, password_file: Path) -> OwnerSetup:
    url = make_url(target.settings.database_url)
    return OwnerSetup(
        host=url.host or "localhost",
        port=url.port or 5432,
        database=target.name,
        superuser=url.username or "",
        superuser_password=url.password or "",
        owner=owner,
        owner_password_file=password_file,
        wait_seconds=0,
    )


async def _as_superuser_made(admin: asyncpg.Connection) -> None:
    """What an installation that ran as the superuser holds: tables with sequences, a
    standalone sequence, a trigger function, a view, an enum and a domain."""
    await admin.execute(
        "CREATE TABLE f21_page (id serial PRIMARY KEY, n int GENERATED ALWAYS AS IDENTITY);"
        "CREATE SEQUENCE f21_counter;"
        "CREATE FUNCTION herd_f21() RETURNS trigger LANGUAGE plpgsql AS"
        " $f$ BEGIN RETURN NEW; END $f$;"
        "CREATE TRIGGER f21 BEFORE INSERT ON f21_page FOR EACH ROW EXECUTE FUNCTION herd_f21();"
        "CREATE VIEW f21_view AS SELECT id FROM f21_page;"
        "CREATE TYPE f21_mood AS ENUM ('ok');"
        "CREATE DOMAIN f21_positive AS int CHECK (VALUE > 0);"
        "INSERT INTO f21_page DEFAULT VALUES"
    )


async def _not_owned(admin: asyncpg.Connection, owner: str) -> list[str]:
    rows = await admin.fetch(
        "SELECT c.relname AS name FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace"
        " AND c.relkind <> 'c' AND pg_get_userbyid(c.relowner) <> $1"
        " UNION ALL SELECT p.proname FROM pg_proc p"
        " WHERE p.pronamespace = 'public'::regnamespace AND pg_get_userbyid(p.proowner) <> $1"
        " UNION ALL SELECT t.typname FROM pg_type t"
        " WHERE t.typnamespace = 'public'::regnamespace AND pg_get_userbyid(t.typowner) <> $1",
        owner,
    )
    return sorted(row["name"] for row in rows)


async def test_the_role_owns_everything_and_is_no_superuser(
    admin: asyncpg.Connection, target: Target, owner: str, tmp_path: Path
) -> None:
    await _as_superuser_made(admin)
    password_file = tmp_path / "secrets" / "db_owner_password"
    password_file.parent.mkdir()
    out = io.StringIO()

    assert await run_db_owner(_setup(target, owner, password_file), out=out) == 0

    password = password_file.read_text()
    assert len(password) == 64 and int(password, 16) >= 0
    assert stat.S_IMODE(password_file.stat().st_mode) == 0o400
    assert password not in out.getvalue() and f"{owner} created" in out.getvalue()
    role = await admin.fetchrow(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin"
        " FROM pg_roles WHERE rolname = $1",
        owner,
    )
    assert tuple(role) == (False, False, False, False, False, True)
    assert (
        await admin.fetchval(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = $1", target.name
        )
        == owner
    )
    assert (
        await admin.fetchval(
            "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'public'"
        )
        == owner
    )
    assert await _not_owned(admin, owner) == []

    # The role signs in with the file's password, may drop and make the schema (what a
    # restore does), and may not run a program on the database host.
    url = make_url(target.settings.database_url).set(username=owner, password=password)
    mine = await asyncpg.connect(asyncpg_dsn(url))
    try:
        swap = mine.transaction()
        await swap.start()
        try:
            await mine.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        finally:
            await swap.rollback()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await mine.execute("COPY (SELECT 1) TO PROGRAM 'true'")
    finally:
        await mine.close()


async def test_every_later_start_keeps_the_password_and_moves_what_is_new(
    admin: asyncpg.Connection, target: Target, owner: str, tmp_path: Path
) -> None:
    password_file = tmp_path / "db_owner_password"
    assert await run_db_owner(_setup(target, owner, password_file), out=io.StringIO()) == 0
    first = password_file.read_text()
    await _as_superuser_made(admin)  # e.g. an operator's psql as the superuser
    await admin.execute(f"ALTER ROLE {owner} CREATEDB")
    out = io.StringIO()

    assert await run_db_owner(_setup(target, owner, password_file), out=out) == 0

    assert password_file.read_text() == first
    assert f"{owner} kept" in out.getvalue()
    assert await _not_owned(admin, owner) == []
    assert not await admin.fetchval("SELECT rolcreatedb FROM pg_roles WHERE rolname = $1", owner)
    url = make_url(target.settings.database_url).set(username=owner, password=first)
    mine = await asyncpg.connect(asyncpg_dsn(url))
    await mine.close()


async def test_a_superuser_role_of_that_name_is_taken_back(
    admin: asyncpg.Connection, target: Target, owner: str, tmp_path: Path
) -> None:
    await admin.execute(f"CREATE ROLE {owner} LOGIN SUPERUSER")
    assert await run_db_owner(_setup(target, owner, tmp_path / "pw"), out=io.StringIO()) == 0
    assert not await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = $1", owner)


async def test_it_refuses_what_it_cannot_use(
    admin: asyncpg.Connection, target: Target, owner: str, tmp_path: Path
) -> None:
    setup = _setup(target, owner, tmp_path / "pw")
    out = io.StringIO()
    assert await run_db_owner(setup._replace(owner=setup.superuser), out=out) == 2
    assert "superuser" in out.getvalue()
    assert await run_db_owner(setup._replace(owner="Herd Owner"), out=io.StringIO()) == 2
    (tmp_path / "empty").write_text("")
    empty = setup._replace(owner_password_file=tmp_path / "empty")
    out = io.StringIO()
    assert await run_db_owner(empty, out=out) == 1
    assert "empty" in out.getvalue()
    wrong = setup._replace(superuser_password="not-the-password", wait_seconds=0)
    out = io.StringIO()
    assert await run_db_owner(wrong, out=out) == 1
    assert "not-the-password" not in out.getvalue()


def test_the_command_line_takes_the_superusers_password_from_a_file_or_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import argparse  # noqa: PLC0415

    from app.stack.__main__ import _owner_setup, main  # noqa: PLC0415 (under test)

    (tmp_path / "db_password").write_text("from-the-file\n")
    file = argparse.Namespace(
        host="db", port=5432, database="herd", superuser="herd", owner="herd_owner",
        superuser_password_file=tmp_path / "db_password", owner_password_file=tmp_path / "pw",
    )  # fmt: skip
    assert _owner_setup(file).superuser_password == "from-the-file"
    monkeypatch.setenv("HERD_DB_SUPERUSER_PASSWORD", "from-the-environment")
    env = argparse.Namespace(**{**vars(file), "superuser_password_file": None})
    setup = _owner_setup(env)
    assert setup.superuser_password == "from-the-environment"
    assert (setup.owner, setup.database, setup.wait_seconds) == ("herd_owner", "herd", 60.0)
    assert main(["db-owner", "--owner", "herd", "--owner-password-file", str(tmp_path / "x")]) == 2
