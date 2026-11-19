"""`python -m app.stack db-owner` (review M9b final, F2-1): the shipped stacks' database
role for the app.

A bundled PostgreSQL makes only its superuser (`POSTGRES_USER`). An archive's dump is
text that runs as the role that restores it, and a superuser may run programs on the
database host (`COPY … TO PROGRAM`). So the stacks run this before the app, as the
superuser, on every start:

- the owner role (`herd_owner`): made once with LOGIN and nothing else; an existing
  role of that name is taken back to LOGIN only (no SUPERUSER, CREATEDB, CREATEROLE,
  REPLICATION, BYPASSRLS);
- its password from `--owner-password-file`: written once (256 random bits as hex, mode
  0400; Hostinger's `init` writes it first), never replaced; an empty file is a broken
  volume (exit 1). The role gets it as a SCRAM verifier, so the clear text never
  reaches the server's statement log;
- the database, its schema `public` and every object in it are handed to the role. An
  installation that ran as the superuser moves on its next start, without a step by
  hand; whatever an operator later makes as the superuser moves on the next start.

Output names roles and counts, never a password. Exit 0, 1 (cannot connect, broken
password file) or 2 (a name it will not use).
"""

import asyncio
import base64
import hashlib
import hmac
import re
import secrets
import time
from pathlib import Path
from typing import NamedTuple, TextIO

import asyncpg

from app.stack.init import BROKEN, INVALID, Refused, ensure_secret, unusable

_ROLE = re.compile(r"[a-z_][a-z0-9_]{0,62}")
_ONLY_LOGIN = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
SCRAM_ITERATIONS = 4096
# The statements that hand every object in `public` to the role ($1), by kind. Linked
# sequences (serial, identity) and a table's row type follow their table; array and
# multirange types follow their element; extension members stay.
_OBJECTS = (
    """SELECT format('ALTER %s %s OWNER TO %I', CASE c.relkind WHEN 'v' THEN 'VIEW'
         WHEN 'm' THEN 'MATERIALIZED VIEW' WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END,
         c.oid::regclass, $1::text)
       FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace
        AND c.relkind IN ('r', 'p', 'v', 'm', 'f') AND pg_get_userbyid(c.relowner) <> $1::text""",
    """SELECT format('ALTER SEQUENCE %s OWNER TO %I', c.oid::regclass, $1::text)
       FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'S'
        AND pg_get_userbyid(c.relowner) <> $1::text AND NOT EXISTS (SELECT 1 FROM pg_depend d
         WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
          AND d.deptype IN ('a', 'i'))""",
    """SELECT format('ALTER ROUTINE %s OWNER TO %I', p.oid::regprocedure, $1::text)
       FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace
        AND pg_get_userbyid(p.proowner) <> $1::text AND NOT EXISTS (SELECT 1 FROM pg_depend d
         WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')""",
    """SELECT format('ALTER %s %s OWNER TO %I',
         CASE t.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END, t.oid::regtype, $1::text)
       FROM pg_type t WHERE t.typnamespace = 'public'::regnamespace
        AND pg_get_userbyid(t.typowner) <> $1::text AND t.typtype IN ('e', 'd', 'r', 'c')
        AND (t.typrelid = 0 OR (SELECT relkind FROM pg_class WHERE oid = t.typrelid) = 'c')
        AND NOT EXISTS (SELECT 1 FROM pg_depend d
         WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e')""",
)


class OwnerSetup(NamedTuple):
    host: str
    port: int
    database: str
    superuser: str
    superuser_password: str
    owner: str
    owner_password_file: Path
    wait_seconds: float = 60.0  # the database may still be starting (the chart's job)


async def run_db_owner(setup: OwnerSetup, *, out: TextIO) -> int:
    def say(line: str) -> None:
        print(f"db-owner: {line}", file=out, flush=True)

    if not _ROLE.fullmatch(setup.owner) or setup.owner == setup.superuser:
        say(f"{setup.owner!r} cannot be the app's role: a plain name (a-z, 0-9, _) other "
            "than the superuser's")  # fmt: skip
        return INVALID
    try:
        ensure_secret(setup.owner_password_file)
        password = setup.owner_password_file.read_text(encoding="utf-8").strip()
    except Refused as refused:
        say(str(refused))
        return BROKEN
    except OSError as failed:
        say(unusable(failed))
        return BROKEN
    try:
        connection = await _connect(setup)
    except (OSError, asyncpg.PostgresError) as failed:
        say(f"cannot reach {setup.database} on {setup.host}:{setup.port} as "
            f"{setup.superuser}: {type(failed).__name__}")  # fmt: skip
        return BROKEN
    try:
        async with connection.transaction():
            made, moved = await _hand_over(connection, setup, password)
    finally:
        await connection.close()
    state = "created" if made else "kept"
    say(f"role {setup.owner} {state}: owns database {setup.database}, schema public and "
        f"every object in it ({moved} handed over), no superuser")  # fmt: skip
    return 0


async def _connect(setup: OwnerSetup) -> asyncpg.Connection:
    deadline = time.monotonic() + setup.wait_seconds
    while True:
        try:
            return await asyncpg.connect(
                host=setup.host,
                port=setup.port,
                user=setup.superuser,
                password=setup.superuser_password,
                database=setup.database,
                timeout=10,
            )
        except (OSError, asyncpg.CannotConnectNowError):
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(1)


async def _hand_over(
    connection: asyncpg.Connection, setup: OwnerSetup, password: str
) -> tuple[bool, int]:
    owner = setup.owner
    made = await connection.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", owner) is None
    if made:
        await connection.execute(f'CREATE ROLE "{owner}" {_ONLY_LOGIN}')
    statements = [
        await connection.fetchval(
            f"SELECT format('ALTER ROLE %I WITH {_ONLY_LOGIN} PASSWORD %L', $1::text, $2::text)",
            owner,
            scram_verifier(password),
        ),
        await connection.fetchval(
            "SELECT format('ALTER DATABASE %I OWNER TO %I', $1::text, $2::text)",
            setup.database,
            owner,
        ),
        await connection.fetchval(
            "SELECT format('ALTER SCHEMA public OWNER TO %I', $1::text)", owner
        ),
    ]
    for statement in statements:
        await connection.execute(statement)
    moved = 0
    for query in _OBJECTS:  # tables before the sequences that are left
        for statement in [row[0] for row in await connection.fetch(query, owner)]:
            await connection.execute(statement)
            moved += 1
    return made, moved


def scram_verifier(password: str) -> str:
    """PostgreSQL's stored form of a SCRAM-SHA-256 password (RFC 5802/7677)."""
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, SCRAM_ITERATIONS)
    client_key = hmac.digest(salted, b"Client Key", "sha256")
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.digest(salted, b"Server Key", "sha256")

    def b64(data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    return f"SCRAM-SHA-256${SCRAM_ITERATIONS}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"
