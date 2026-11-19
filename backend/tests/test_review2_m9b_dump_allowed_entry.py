"""Review M9b final, finding F2-1: the fix of F1 judges a dump's entries by kind and
name only. The definition of an allowed entry is still the archive's text, so the
scenario F1 named (an uploaded archive runs a program on the database host, as the
superuser role the shipped stacks give the application) still works: through an
entry the allow-list lets pass. No hex editor is needed: this dump is what plain
`pg_dump` writes for a database someone prepared (a function under one of the seven
allowed names, used by a table's CHECK constraint)."""

import asyncio
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path

import pytest

from app.ops.dump_toc import list_dump
from app.ops.pgtools import ToolFailed, child_env
from app.ops.swap import swap_database
from tests.factories_restore import Target
from tests.replace_helpers import scalar, sql


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _prepared_dump(target: Target, tmp_path: Path, proof: Path) -> bytes:
    """A plain pg_dump of a database whose function `herd_work_item_hierarchy()` (an
    allowed name) runs a program, called by a CHECK constraint when the data loads."""
    head = "FUNCTION herd_work_item_hierarchy() RETURNS boolean LANGUAGE plpgsql AS "
    await sql(target.settings, f"CREATE {head} $f$ BEGIN RETURN true; END $f$")
    await sql(target.settings, "CREATE TABLE note (a int CHECK (herd_work_item_hierarchy()))")
    await sql(target.settings, "INSERT INTO note VALUES (1)")
    # Only now the body that runs a program: nothing runs while the dump is prepared.
    await sql(
        target.settings,
        f"CREATE OR REPLACE {head} "
        f"$f$ BEGIN COPY (SELECT 1) TO PROGRAM 'touch {proof}'; RETURN true; END $f$",
    )
    out = tmp_path / "prepared.dump"
    process = await asyncio.create_subprocess_exec(
        "pg_dump", "--format=custom", "--no-password", f"--file={out}",
        env=child_env(target.settings),
    )  # fmt: skip
    assert await process.wait() == 0
    await sql(target.settings, "DROP TABLE note")
    await sql(target.settings, "DROP FUNCTION herd_work_item_hierarchy()")
    return out.read_bytes()


async def test_an_allowed_entry_cannot_run_a_program_on_the_database_host(
    target: Target, tmp_path: Path
) -> None:
    if not await scalar(
        target.settings, "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    ):
        pytest.skip("the test role is no superuser")
    proof = Path(tempfile.gettempdir()) / f"herd-review2-m9b-{uuid.uuid4().hex}"
    dump = await _prepared_dump(target, tmp_path, proof)
    assert not await scalar(
        target.settings, f"SELECT (pg_stat_file('{proof}', true)).size IS NOT NULL"
    ), "preparing the dump must not run the program"

    try:
        # "Prüfen" judges the dump as ours ...
        await list_dump(_chunks(dump))
        # ... and "Einspielen" runs it.
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
