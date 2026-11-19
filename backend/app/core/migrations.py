"""Alembic from code: the config, `upgrade head`, and whether this code fits the schema."""

from enum import StrEnum
from functools import cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "alembic"
# Migrating and restoring an archive (`app/ops/restore.py`) take this advisory lock, so
# a process starting in role `all` never migrates a database that is being restored.
SCHEMA_LOCK = "herd.schema"


def alembic_config() -> Config:
    """Built without alembic.ini: only the script location is needed; env.py sets the URL."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def upgrade_head(connection: Connection | None = None) -> None:
    """Migrate to head; on `connection`, inside its transaction, when one is given (tests)."""
    config = alembic_config()
    if connection is not None:
        config.attributes["connection"] = connection
    command.upgrade(config, "head")


def lock_schema(connection: Connection) -> None:
    """Hold SCHEMA_LOCK until the connection's transaction ends (alembic's env.py)."""
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:name, 0))"), {"name": SCHEMA_LOCK}
    )


def known_revisions() -> tuple[frozenset[str], frozenset[str]]:
    """The code's heads and every revision it knows."""
    return _code_revisions()


def stamp_head(connection: Connection) -> None:
    """Record the head revision on `connection` without running migrations (tests)."""
    config = alembic_config()
    config.attributes["connection"] = connection
    command.stamp(config, "head")


def _database_heads(connection: Connection) -> set[str]:
    # Read directly rather than through MigrationContext, which logs two INFO lines on
    # every call, i.e. on every readiness probe.
    if connection.execute(text("SELECT to_regclass('alembic_version')")).scalar() is None:
        return set()
    return set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())


@cache
def _code_revisions() -> tuple[frozenset[str], frozenset[str]]:
    """The chain's heads and every revision it knows; fixed while the process runs."""
    script = ScriptDirectory.from_config(alembic_config())
    known = frozenset(rev.revision for rev in script.walk_revisions())
    return frozenset(script.get_heads()), known


class SchemaState(StrEnum):
    NONE = "none"  # no revision recorded
    HEAD = "head"  # the code's head
    BEHIND = "behind"  # a known, older revision: migrate first
    AHEAD = "ahead"  # a revision this code does not know: a newer release migrated


async def schema_state(engine: AsyncEngine) -> SchemaState:
    """Where the database's schema stands against this code's migrations."""
    async with engine.connect() as connection:
        database = await connection.run_sync(_database_heads)
    heads, known = _code_revisions()
    if not database:
        return SchemaState.NONE
    if database == heads:
        return SchemaState.HEAD
    return SchemaState.BEHIND if database <= known else SchemaState.AHEAD


async def schema_is_compatible(engine: AsyncEngine) -> bool:
    """Whether this code may serve the database's schema.

    True when the database stands at the code's head, or at a revision this code does
    not know: a newer release has migrated (pre-upgrade) and its migrations are
    backward compatible with this release (expand first, contract a release later).
    False when the database has no revision or stands at a known, older one.
    """
    async with engine.connect() as connection:
        database = await connection.run_sync(_database_heads)
    heads, known = _code_revisions()
    # An empty set is a subset of `known`, so "no revision" is not compatible.
    return database == heads or not database <= known
