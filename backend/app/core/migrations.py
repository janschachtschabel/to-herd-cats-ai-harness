"""Alembic from code: the config, `upgrade head`, and whether the schema is current."""

from functools import cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "alembic"


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
def _head_revisions() -> frozenset[str]:
    """The chain's heads; they cannot change while the process runs."""
    return frozenset(ScriptDirectory.from_config(alembic_config()).get_heads())


async def schema_is_current(engine: AsyncEngine) -> bool:
    """True when the database stands at the head revision(s) of the migration chain."""
    async with engine.connect() as connection:
        return await connection.run_sync(_database_heads) == _head_revisions()
