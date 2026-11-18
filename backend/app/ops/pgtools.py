"""PostgreSQL's own tools as child processes (plan M9 decision 2): `pg_dump -Fc` for
backups, `pg_restore` for restores.

A child gets an environment built here and nothing else of the app's: `PATH`, the
`PG*` connection variables and `PGPASSWORD`. The password is never in an argument list
(`ps` shows those) or a URL. What a tool writes to stderr is not logged (it may name
tables or values); a failure is a code and the exit status.
"""

import asyncio
import os
import re
import shutil
import subprocess
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import Settings

_VERSION = re.compile(r"\(PostgreSQL\)\s+(\d+)(?:\.(\d+))?")
# The asyncpg URL's TLS option, as libpq names it.
_SSL_QUERY = ("sslmode", "ssl")


class ToolFailed(Exception):
    """A tool is missing or ended with an error; `code` says which."""

    def __init__(self, code: str, status: int | None = None) -> None:
        super().__init__(code if status is None else f"{code} (exit {status})")
        self.code = code
        self.status = status


def child_env(settings: Settings) -> dict[str, str]:
    """The whole environment of a PostgreSQL tool: where to connect (the schema owner
    when roles are separate, J14), the password and TLS."""
    url = settings.migrate_database()
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C.UTF-8"}
    for name, value in (
        ("PGHOST", url.host),
        ("PGPORT", str(url.port) if url.port else None),
        ("PGUSER", url.username),
        ("PGDATABASE", url.database),
        ("PGPASSWORD", url.password),
    ):
        if value:
            env[name] = str(value)
    for key in _SSL_QUERY:
        mode = url.query.get(key)
        if isinstance(mode, str) and mode:
            env["PGSSLMODE"] = mode
    # HERD_DATABASE_SSLMODE/-SSLROOTCERT win over the URL (J12 a), as for asyncpg.
    if settings.database_sslmode:
        env["PGSSLMODE"] = settings.database_sslmode
    if settings.database_sslrootcert is not None:
        env["PGSSLROOTCERT"] = str(settings.database_sslrootcert)
    return env


async def server_major(conn: AsyncConnection) -> int:
    return int(await conn.scalar(text("SHOW server_version_num")) or 0) // 10000


def tool_version(tool: str) -> str:
    """`16.15` for `pg_dump (PostgreSQL) 16.15 (...)`; ToolFailed if missing."""
    path = shutil.which(tool)
    if path is None:
        raise ToolFailed("backup.tool_missing")
    out = subprocess.run(  # noqa: S603 (a fixed tool from PATH, no shell)
        [path, "--version"], capture_output=True, text=True, timeout=30, check=False
    ).stdout
    match = _VERSION.search(out)
    if match is None:
        raise ToolFailed("backup.tool_missing")
    return match.group(1) + (f".{match.group(2)}" if match.group(2) else "")


def client_major(tool: str) -> int:
    return int(tool_version(tool).split(".")[0])


# The first releases whose pg_restore writes `\restrict <key>` around a dump's SQL and
# whose psql refuses backslash commands inside it (CVE-2025-8714); 18 has it from .0.
RESTRICT_SINCE = {16: 10, 17: 6}


def restrict_capable(version: str) -> bool:
    """Whether a tool of `version` (`tool_version`) knows `\\restrict`."""
    major, _, minor = version.partition(".")
    if int(major) >= 18:
        return True
    since = RESTRICT_SINCE.get(int(major))
    return since is not None and int(minor or 0) >= since


def require_restrict(*tools: str) -> None:
    """ToolFailed `restore.tools_too_old` unless every tool knows `\\restrict`
    (`restore.tool_missing` if one is missing)."""
    for tool in tools:
        try:
            version = tool_version(tool)
        except ToolFailed:
            raise ToolFailed("restore.tool_missing") from None
        if not restrict_capable(version):
            raise ToolFailed("restore.tools_too_old")


async def dump(settings: Settings, snapshot_id: str, out: Path) -> None:
    """`pg_dump -Fc` of the database in the exported snapshot `snapshot_id` (its
    transaction stays open meanwhile) into `out`."""
    path = shutil.which("pg_dump")
    if path is None:
        raise ToolFailed("backup.tool_missing")
    process = await asyncio.create_subprocess_exec(
        path,
        "--format=custom",
        "--no-password",
        f"--snapshot={snapshot_id}",
        f"--file={out}",
        env=child_env(settings),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    status = await process.wait()
    if status != 0:
        raise ToolFailed("backup.dump_failed", status)


async def restore(settings: Settings, dump: AsyncIterator[bytes], *, use_list: str) -> None:
    """`pg_restore` of the custom-format dump read from `dump` (piped to its stdin, no
    scratch file) into the settings' database: all or nothing (`--single-transaction
    --exit-on-error`), without owners and grants (managed databases have other
    roles), only the entries of `use_list` (`dump_toc.list_dump`)."""
    path = shutil.which("pg_restore")
    if path is None:
        raise ToolFailed("restore.tool_missing")
    env = child_env(settings)
    with use_list_file(use_list) as (list_fd, list_path):
        process = await asyncio.create_subprocess_exec(
            path,
            "--no-owner",
            "--no-privileges",
            "--single-transaction",
            "--exit-on-error",
            "--no-password",
            f"--use-list={list_path}",
            f"--dbname={env.get('PGDATABASE', '')}",
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            pass_fds=(list_fd,),
        )
    stdin = process.stdin
    assert stdin is not None  # PIPE above
    try:
        async for chunk in dump:
            stdin.write(chunk)
            await stdin.drain()
        stdin.close()
        await stdin.wait_closed()
    except (BrokenPipeError, ConnectionResetError):
        pass  # pg_restore stopped reading: its exit status says why
    except BaseException:
        process.kill()
        await process.wait()
        raise
    status = await process.wait()
    if status != 0:
        raise ToolFailed("restore.pg_restore_failed", status)


@contextmanager
def use_list_file(content: str) -> Iterator[tuple[int, str]]:
    """A `--use-list` file in memory (no scratch file on disk): its descriptor (for
    `pass_fds`) and the path a child opens it by."""
    fd = os.memfd_create("herd-use-list", 0)
    try:
        data = memoryview(content.encode())
        while data:
            data = data[os.write(fd, data) :]
        yield fd, f"/dev/fd/{fd}"
    finally:
        os.close(fd)
