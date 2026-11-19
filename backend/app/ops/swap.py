"""The database swap of a replace (plan M9 decision 9): one `psql` session, one
transaction, all or nothing.

    BEGIN; SET LOCAL lock_timeout;
    CREATE TEMPORARY TABLE herd_swap_<token> ON COMMIT DROP (this transaction's id);
    DROP SCHEMA public CASCADE; CREATE SCHEMA public;
    <the archive's dump as SQL, from `pg_restore --file=-`, within `\\restrict <key>`>
    <`tail_sql`: maintenance stays on in the restored state>
    <the check that this is still the transaction of the temporary table>
    COMMENT ON SCHEMA public IS 'herd-swap <token>';
    COMMIT;

The dump goes from the archive through pg_restore's stdin, its SQL from pg_restore's
stdout into psql's stdin: no scratch file. COMMIT is sent only once pg_restore ended
well; on any failure psql is killed before it reads a COMMIT, and its connection's
end rolls the transaction back (psql's own `--single-transaction` would commit at the
end of its input, a cut-off script included). `ON_ERROR_STOP` ends psql at the first
error. The lock timeout bounds the wait for the tables (a transaction left open
somewhere): the swap fails instead of holding every query behind it.

What the dump may run (review M9b F1): only the entries of its table of contents that
`dump_toc.py` judges ours (`archive.dump_foreign` otherwise), inside psql's
`\\restrict` with a key of ours (pg_restore and psql must know it,
`restore.tools_too_old`), and a dump that ends the transaction itself (a `COMMIT` in a
definition) fails the check before our COMMIT. Whenever the swap does not end well,
or after a cancel (review M9b F5), the database says which state it holds
(`swap_outcome.py`): rolled back raises the failure as it came (the old state is
whole); committed by us after all returns, or raises `SwapCommitted` after a cancel;
anything else raises `SwapUncertain` (`restore.swap_broken`,
`restore.swap_unknown`): the old state may be gone.

As in `pgtools.py`: the children get only the environment built there, of their
output only a connection-level error line is logged (`tool_errors.py`), a failure is
a code (`restore.tool_missing`, `restore.pg_restore_failed`, `restore.swap_failed`).
"""

import asyncio
import secrets
import shutil
from collections.abc import AsyncIterator
from contextlib import suppress

from app.core.config import Settings
from app.ops import tool_errors
from app.ops.dump_toc import list_dump
from app.ops.pgtools import ToolFailed, child_env, require_restrict, use_list_file
from app.ops.swap_outcome import (
    Outcome,
    app_name,
    clear_marker,
    marker,
    schema_oid,
    settle,
)

LOCK_TIMEOUT = "60s"
CHUNK = 1024 * 1024


class SwapUncertain(ToolFailed):
    """The swap did not end well and the old state may be gone: maintenance stays on."""


class SwapCommitted(ToolFailed):
    """Interrupted after the swap committed: the database holds the archive, not yet
    finished (`restore.finish_failed`)."""


def head_sql(token: str) -> str:
    return (
        "BEGIN;\n"
        f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}';\n"
        f"CREATE TEMPORARY TABLE herd_swap_{token} (xid pg_catalog.xid8) ON COMMIT DROP;\n"
        f"INSERT INTO pg_temp.herd_swap_{token} VALUES (pg_catalog.pg_current_xact_id());\n"
        "DROP SCHEMA public CASCADE;\n"
        "CREATE SCHEMA public;\n"
    )


def tail_of(tail_sql: str, token: str) -> str:
    # No input reaches this text: `tail_sql` is made by this code, the token here.
    return (
        tail_sql + "DO $herd$ BEGIN\n"
        "  IF NOT EXISTS (SELECT FROM pg_temp.herd_swap_" + token + "\n"
        "      WHERE xid = pg_catalog.pg_current_xact_id()) THEN\n"
        "    RAISE EXCEPTION 'the swap''s transaction ended early';\n"
        "  END IF;\n"
        "END $herd$;\n"
        f"COMMENT ON SCHEMA public IS '{marker(token)}';\n"
        "COMMIT;\n"
    )


async def swap_database(settings: Settings, dump: AsyncIterator[bytes], *, tail_sql: str) -> None:
    pg_restore, psql = shutil.which("pg_restore"), shutil.which("psql")
    if pg_restore is None or psql is None:
        raise ToolFailed("restore.tool_missing")
    require_restrict(pg_restore, psql)
    listing = await list_dump(dump)
    token = secrets.token_hex(16)
    before = await schema_oid(settings)
    env = child_env(settings)
    with use_list_file(listing.use_list) as (list_fd, list_path):
        session = await asyncio.create_subprocess_exec(
            psql,
            "--no-psqlrc",
            "--quiet",
            "--no-password",
            "--set=ON_ERROR_STOP=1",
            f"--dbname={env.get('PGDATABASE', '')}",
            "--file=-",
            env={**env, "PGAPPNAME": app_name(token)},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        script = await _start_or_kill(
            session,
            pg_restore,
            "--no-owner",
            "--no-privileges",
            f"--use-list={list_path}",
            f"--restrict-key={secrets.token_hex(32)}",
            "--file=-",
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            pass_fds=(list_fd,),
        )
    said = {"psql": tool_errors.collect(session.stderr)}
    said["pg_restore"] = tool_errors.collect(script.stderr)
    try:
        await _run(session, script, listing.dump, token, tail_sql)
    except BaseException as exc:
        await _stop(session, script)
        if type(exc) is ToolFailed:
            tool = "pg_restore" if exc.code == "restore.pg_restore_failed" else "psql"
            await tool_errors.log_failure(tool, exc.code, exc.status, said[tool])
        await _after_failure(settings, token, before, exc)
        return
    finally:
        for task in said.values():
            task.cancel()
    if await settle(settings, token, before) != Outcome.SWAPPED:
        raise SwapUncertain("restore.swap_unknown")
    await clear_marker(settings)


async def _stop(session: asyncio.subprocess.Process, script: asyncio.subprocess.Process) -> None:
    for process in (session, script):  # the session first: nothing commits
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()


async def _start_or_kill(
    session: asyncio.subprocess.Process, *args: str, **kwargs: object
) -> asyncio.subprocess.Process:
    """pg_restore; if it cannot start, the waiting psql session ends (nothing ran)."""
    try:
        return await asyncio.create_subprocess_exec(*args, **kwargs)  # type: ignore[arg-type]
    except BaseException:
        with suppress(ProcessLookupError):
            session.kill()
        await session.wait()
        raise


async def _after_failure(settings: Settings, token: str, before: int, exc: BaseException) -> None:
    """Raise what the state the database holds calls for (returns if the swap
    committed after all, for a failure that was no interruption)."""
    outcome = await settle(settings, token, before)
    if outcome == Outcome.KEPT:
        raise exc
    if outcome == Outcome.SWAPPED:
        await clear_marker(settings)
        if isinstance(exc, Exception):
            return
        raise SwapCommitted("restore.finish_failed") from exc
    raise SwapUncertain(f"restore.swap_{outcome.value}") from exc


async def _run(
    session: asyncio.subprocess.Process,
    script: asyncio.subprocess.Process,
    dump: AsyncIterator[bytes],
    token: str,
    tail_sql: str,
) -> None:
    sql_in, dump_in, sql_out = session.stdin, script.stdin, script.stdout
    assert sql_in is not None and dump_in is not None and sql_out is not None  # PIPEs
    sql_in.write(head_sql(token).encode())
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
        sql_in.write(tail_of(tail_sql, token).encode())
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
