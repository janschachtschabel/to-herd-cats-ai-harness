"""Separate database roles (plan M9 task 18, J14; ASVS 5.0 V13.2.2), an option.

The migration role (HERD_MIGRATE_DATABASE_URL) owns the schema: migrations, backups and
restores connect with it (`Settings.migrate_database`). The runtime role
(HERD_DATABASE_RUNTIME_ROLE, the user of HERD_DATABASE_URL) gets data rights only:
`grant_runtime_role` runs at the end of every migration run (`alembic/env.py`), so the
rights cover every table and sequence, including a role named only later, and
`ALTER DEFAULT PRIVILEGES` covers what later migrations create. CREATE on schema
`public` is taken from PUBLIC (PostgreSQL 15 and later do that already). Of
`alembic_version` the runtime role may only read (for `/ready`).

Without HERD_DATABASE_RUNTIME_ROLE nothing is granted: one role does everything, as
before."""

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

DATA = "SELECT, INSERT, UPDATE, DELETE"
NUMBERS = "USAGE, SELECT, UPDATE"


def runtime_grants(role: str) -> list[str]:
    """The statements; `role` is a plain name (`config_database` checks it), quoted."""
    who = '"' + role.replace('"', '""') + '"'
    return [
        f"GRANT USAGE ON SCHEMA public TO {who}",
        f"GRANT {DATA} ON ALL TABLES IN SCHEMA public TO {who}",
        f"GRANT {NUMBERS} ON ALL SEQUENCES IN SCHEMA public TO {who}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT {DATA} ON TABLES TO {who}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT {NUMBERS} ON SEQUENCES TO {who}",
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        # The recorded revision is the migration role's to write; `/ready` only reads
        # it (R18-8). The runs before granted it with ALL TABLES above.
        f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON alembic_version FROM {who}",
    ]


def grant_runtime_role(connection: Connection, role: str) -> None:
    """Give `role` the data rights, inside the connection's transaction."""
    for statement in runtime_grants(role):
        connection.execute(text(statement))


# The connected role may restore: it owns (or is a member of the owner of) schema
# `public`, which the swap drops (the database's owner is a member of
# `pg_database_owner`, the default owner; review M9b F2-6), can create in it, and owns
# every table there.
_OWNS_SCHEMA = text(
    "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'public'"
    " AND pg_has_role(current_user, nspowner, 'USAGE'))"
    " AND has_schema_privilege('public', 'CREATE') AND NOT EXISTS ("
    " SELECT 1 FROM pg_tables WHERE schemaname = 'public'"
    " AND NOT pg_has_role(current_user, tableowner, 'USAGE'))"
)


_SUPERUSER = text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
SUPERUSER_REFUSED = "restore.superuser_refused"


async def superuser_problem(conn: AsyncConnection) -> str | None:
    """`restore.superuser_refused` when this connection's role is a superuser (review
    M9b F2-1): an archive's definitions are text that runs as the restoring role, and
    a superuser may run programs on the database host (`COPY … TO PROGRAM`). The
    administration never replaces as one; the command line only when told
    (`--allow-superuser`)."""
    return SUPERUSER_REFUSED if await conn.scalar(_SUPERUSER) else None


async def schema_owner_problem(conn: AsyncConnection) -> str | None:
    """`restore.not_schema_owner` when this connection's role could not restore (the
    runtime role of separate roles); a restore needs the migration role."""
    owns = await conn.scalar(_OWNS_SCHEMA)
    return None if owns else "restore.not_schema_owner"
