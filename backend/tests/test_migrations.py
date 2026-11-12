"""The rollback path has to exist, not just the way forward.

Alembic autogenerates `create_foreign_key(None, ...)` and the matching
`drop_constraint(None, ...)`, and the unnamed drop cannot be compiled at all.
Nothing notices until someone actually needs to roll back, which is the worst
moment to find out. Rendering the whole chain offline needs no database.
"""

import io
import logging
from contextlib import redirect_stdout
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection

from app.core.migrations import alembic_config
from app.models_registry import Base

ROOT = Path(__file__).resolve().parent.parent


def test_every_migration_can_be_rolled_back() -> None:
    """`--sql` mode compiles every operation without touching a database."""
    out = io.StringIO()
    with redirect_stdout(out):
        command.downgrade(alembic_config(), "head:base", sql=True)
    assert "DROP TABLE organization" in out.getvalue()


def test_every_migration_can_be_applied() -> None:
    with redirect_stdout(io.StringIO()):
        command.upgrade(alembic_config(), "base:head", sql=True)


def test_rendering_the_chain_leaves_the_rest_of_the_suite_alone() -> None:
    """Alembic's env.py would call `fileConfig` when handed an ini file, and that
    disables every logger already in the process. A test that silences the logging
    of everything running after it is not a test that minds its own state."""
    probe = logging.getLogger("app.probe.migrations")
    assert probe.disabled is False

    with redirect_stdout(io.StringIO()):
        command.upgrade(alembic_config(), "base:head", sql=True)

    assert probe.disabled is False
    assert logging.getLogger().handlers, "root handlers must survive env.py"


def test_the_cli_config_leaves_logging_alone() -> None:
    """`alembic.ini` is what the CLI reads; rendering through it must not run fileConfig."""
    probe = logging.getLogger("app.probe.migrations.cli")
    with redirect_stdout(io.StringIO()):
        command.upgrade(Config(str(ROOT / "alembic.ini")), "base:head", sql=True)

    assert probe.disabled is False


def _model_drift(connection: Connection) -> list[object]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


async def test_migrated_schema_matches_the_models(engine) -> None:
    """The test database is built by `upgrade head` (conftest); autogenerate against it
    must find nothing to do, or models and migrations have drifted apart."""
    async with engine.connect() as conn:
        assert await conn.run_sync(_model_drift) == []
