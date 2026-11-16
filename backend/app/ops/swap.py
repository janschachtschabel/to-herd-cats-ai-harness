"""The database swap of a replace (plan M9 decision 9): one `psql` session, one
transaction, all or nothing.

    BEGIN; SET LOCAL lock_timeout; DROP SCHEMA public CASCADE; CREATE SCHEMA public;
    <the archive's dump as SQL, from `pg_restore --file=-`>
    <`tail_sql`: maintenance stays on in the restored state>
    COMMIT;

The dump goes from the archive through pg_restore's stdin, its SQL from pg_restore's
stdout into psql's stdin: no scratch file. COMMIT is sent only once pg_restore ended
well; on any failure psql is killed before it reads a COMMIT, and its connection's
end rolls the transaction back (psql's own `--single-transaction` would commit at the
end of its input, a cut-off script included). `ON_ERROR_STOP` ends psql at the first
error. The lock timeout bounds the wait for the tables (a transaction left open
somewhere): the swap fails instead of holding every query behind it.

As in `pgtools.py`: the children get only the environment built there, nothing of
their output is logged, a failure is a code (`restore.tool_missing`,
`restore.pg_restore_failed`, `restore.swap_failed`).
"""

import asyncio
import shutil
from collections.abc import AsyncIterator
from contextlib import suppress

from app.core.config import Settings
from app.ops.pgtools import ToolFailed, child_env

LOCK_TIMEOUT = "60s"
CHUNK = 1024 * 1024
HEAD_SQL = (
    "BEGIN;\n"
    f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}';\n"
    "DROP SCHEMA public CASCADE;\n"
    "CREATE SCHEMA public;\n"
)


async def swap_database(settings: Settings, dump: AsyncIterator[bytes], *, tail_sql: str) -> None:
    pg_restore, psql = shutil.which("pg_restore"), shutil.which("psql")
    if pg_restore is None or psql is None:
        raise ToolFailed("restore.tool_missing")
    env = child_env(settings)
    session = await asyncio.create_subprocess_exec(
        psql,
        "--no-psqlrc",
        "--quiet",
        "--no-password",
        "--set=ON_ERROR_STOP=1",
        f"--dbname={env.get('PGDATABASE', '')}",
        "--file=-",
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    script = await asyncio.create_subprocess_exec(
        pg_restore,
        "--no-owner",
        "--no-privileges",
        "--file=-",
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await _run(session, script, dump, tail_sql)
    except BaseException:
        for process in (session, script):  # the session first: nothing commits
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
        raise


async def _run(
    session: asyncio.subprocess.Process,
    script: asyncio.subprocess.Process,
    dump: AsyncIterator[bytes],
    tail_sql: str,
) -> None:
    sql_in, dump_in, sql_out = session.stdin, script.stdin, script.stdout
    assert sql_in is not None and dump_in is not None and sql_out is not None  # PIPEs
    sql_in.write(HEAD_SQL.encode())
    tasks = [asyncio.create_task(_feed(dump, dump_in)), asyncio.create_task(_pass(sql_out, sql_in))]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.wait(tasks)
    for task in tasks:
        if task.cancelled():
            continue
        failure = task.exception()
        if isinstance(failure, BrokenPipeError | ConnectionResetError):
            raise ToolFailed("restore.swap_failed")  # psql stopped: an SQL error
        if failure is not None:
            raise failure
    if await script.wait() != 0:
        raise ToolFailed("restore.pg_restore_failed", script.returncode)
    try:
        sql_in.write(tail_sql.encode() + b"COMMIT;\n")
        await sql_in.drain()
        sql_in.close()
        await sql_in.wait_closed()
    except (BrokenPipeError, ConnectionResetError):
        pass  # psql stopped: its exit status says why
    status = await session.wait()
    if status != 0:
        raise ToolFailed("restore.swap_failed", status)


async def _feed(dump: AsyncIterator[bytes], into: asyncio.StreamWriter) -> None:
    try:
        async for chunk in dump:
            into.write(chunk)
            await into.drain()
        into.close()
        await into.wait_closed()
    except (BrokenPipeError, ConnectionResetError):
        pass  # pg_restore stopped reading: its exit status says why


async def _pass(source: asyncio.StreamReader, into: asyncio.StreamWriter) -> None:
    while chunk := await source.read(CHUNK):
        into.write(chunk)
        await into.drain()
