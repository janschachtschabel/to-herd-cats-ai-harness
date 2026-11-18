"""Alembic environment (async). The URL is the app's: HERD_DATABASE_URL with
HERD_DATABASE_PASSWORD(_FILE) merged in (`Settings.database()`). It is handed over as
a URL object, never through the ini config, whose interpolation would mangle a `%`
in an escaped password.

No `fileConfig`: it would disable every logger already in the process. Logging is
configured once by the application; a bare CLI run gets the same JSON/text logging.
"""

import asyncio
import logging

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import make_engine
from app.core.db_roles import grant_runtime_role
from app.core.logging import configure_logging
from app.core.migrations import lock_schema
from app.models_registry import Base

if not logging.getLogger().handlers:  # the alembic CLI; the app has configured logging
    configure_logging(get_settings())

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().migrate_database(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        lock_schema(connection)  # never while an archive is being restored (plan M9)
        context.run_migrations()
        # Separate roles (J14): the runtime role's data rights, after every run, so a
        # role named later and every new table are covered (core/db_roles.py).
        if role := get_settings().database_runtime_role:
            grant_runtime_role(connection, role)


async def run_migrations_online() -> None:
    engine = make_engine(get_settings().migrate_database(), poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif isinstance(connection := config.attributes.get("connection"), Connection):
    _run(connection)  # handed a connection (tests): migrate on it, inside its transaction
else:
    asyncio.run(run_migrations_online())
