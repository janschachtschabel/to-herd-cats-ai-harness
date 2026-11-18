"""Review M9b, finding F1: the swap of a replace runs whatever SQL the archive's dump
turns into, with the application's database role. An owner uploads an archive in the
administration (Task 13), so the dump is input from a browser, not the operator's.

`pg_dump -Fc` keeps each object's definition as plain text in the dump's table of
contents; a changed definition goes into psql unchanged. These tests change one
comment's text (same length, so the dump stays readable) the way anyone with a hex
editor can."""

import asyncio
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path

import pytest

from app.ops.pgtools import ToolFailed, child_env
from app.ops.swap import swap_database
from tests.factories_restore import Target
from tests.replace_helpers import scalar, sql

FILLER = "X" * 300


async def _dump_with(target: Target, tmp_path: Path, injected: str) -> bytes:
    """A custom-format dump of a one-table database whose comment's definition was
    replaced by `injected` (padded to the same length)."""
    await sql(target.settings, "CREATE TABLE note (a int)")
    await sql(target.settings, f"COMMENT ON TABLE note IS '{FILLER}'")
    out = tmp_path / "source.dump"
    process = await asyncio.create_subprocess_exec(
        "pg_dump", "--format=custom", "--no-password", f"--file={out}",
        env=child_env(target.settings),
    )  # fmt: skip
    assert await process.wait() == 0
    data = out.read_bytes()
    assert data.count(FILLER.encode()) == 1
    assert len(injected) <= len(FILLER)
    return data.replace(FILLER.encode(), injected.ljust(len(FILLER)).encode())


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def test_a_dump_that_commits_by_itself_does_not_destroy_the_old_state(
    target: Target, tmp_path: Path
) -> None:
    """`swap.py`: "COMMIT is sent only once pg_restore ended well ... on any failure
    ... the transaction rolls back", `replace.py`: "If anything here fails, the old
    state is whole". A dump whose SQL says COMMIT itself and then fails ends both."""
    dump = await _dump_with(target, tmp_path, "x'; COMMIT; SELECT 1/0; --")
    await sql(target.settings, "CREATE TABLE old_state (a int)")
    await sql(target.settings, "INSERT INTO old_state VALUES (1)")

    with pytest.raises(ToolFailed):
        await swap_database(target.settings, _chunks(dump), tail_sql="")

    # The swap failed, so the replaced installation must be as it was.
    assert await scalar(target.settings, "SELECT to_regclass('public.old_state')") is not None


async def test_a_dump_cannot_run_a_program_on_the_database_host(
    target: Target, tmp_path: Path
) -> None:
    """The shipped stacks (deploy/compose, the Hostinger docker-compose.yml) give the
    application the role POSTGRES_USER, a superuser; so does this test's database. An
    uploaded archive must not be able to use that (COPY ... TO PROGRAM)."""
    if not await scalar(
        target.settings, "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    ):
        pytest.skip("the test role is no superuser")
    # Where the database server's own user may write (it runs the program).
    proof = Path(tempfile.gettempdir()) / f"herd-review-m9b-{uuid.uuid4().hex}"
    dump = await _dump_with(target, tmp_path, f"x'; COPY (SELECT 1) TO PROGRAM 'touch {proof}'; --")

    try:
        with suppress(ToolFailed):  # refusing the dump is fine; running it is not
            await swap_database(target.settings, _chunks(dump), tail_sql="")
        ran = bool(
            await scalar(
                target.settings, f"SELECT (pg_stat_file('{proof}', true)).size IS NOT NULL"
            )
        )
        assert not ran, "the uploaded dump ran a shell command as the database server"
    finally:
        await sql(target.settings, f"COPY (SELECT 1) TO PROGRAM 'rm -f {proof}'")
