"""The swap of a replace never assumes the state it leaves (review M9b F1 c, F5): a
dump that ends the transaction itself is found out before our COMMIT and reported as
`restore.swap_broken` (maintenance stays on, nothing claims the old state); a replace
interrupted once the swap committed keeps the archive's state and its files
(`restore.finish_failed`) instead of taking them away."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from app.ops import swap
from app.ops.pgtools import child_env
from app.ops.replace import replace_running
from app.ops.restore import RestoreFailed
from app.ops.swap import SwapUncertain, swap_database
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.replace_helpers import NAME, marked, running, scalar, sql
from tests.support.clock import SettableClock

FILLER = "X" * 120
ACTIVE = "SELECT count(*) FROM maintenance WHERE active"
FAILED = "SELECT details->>'code' FROM audit_log WHERE action = 'backup.restore_failed'"
COMMENT = "SELECT obj_description('public'::regnamespace, 'pg_namespace')"


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _table_dump_with(target: Target, tmp_path: Path, injected: str) -> bytes:
    """A dump whose only table's definition (an allowed entry) carries `injected`."""
    await sql(target.settings, f"CREATE TABLE note (a text CHECK (a <> '{FILLER}'))")
    out = tmp_path / "source.dump"
    process = await asyncio.create_subprocess_exec(
        "pg_dump", "--format=custom", "--no-password", f"--file={out}",
        env=child_env(target.settings),
    )  # fmt: skip
    assert await process.wait() == 0
    data = out.read_bytes()
    assert data.count(FILLER.encode()) == 1
    return data.replace(FILLER.encode(), injected.ljust(len(FILLER)).encode())


async def test_a_dump_that_ends_the_transaction_itself_is_found_broken(
    target: Target, tmp_path: Path
) -> None:
    dump = await _table_dump_with(target, tmp_path, "x'::text))); COMMIT; --")
    await sql(target.settings, "CREATE TABLE old_state (a int)")

    with pytest.raises(SwapUncertain) as uncertain:
        await swap_database(target.settings, _chunks(dump), tail_sql="")

    assert uncertain.value.code == "restore.swap_broken"
    # Our COMMIT never ran: the check before it failed (no marker on the schema).
    assert await scalar(target.settings, COMMENT) is None


async def test_a_dump_that_rolls_back_itself_leaves_the_old_state(
    target: Target, tmp_path: Path
) -> None:
    dump = await _table_dump_with(target, tmp_path, "x'::text))); ROLLBACK; --")
    await sql(target.settings, "CREATE TABLE old_state (a int)")

    with pytest.raises(swap.ToolFailed) as failed:
        await swap_database(target.settings, _chunks(dump), tail_sql="")

    assert failed.value.code == "restore.swap_failed"
    assert not isinstance(failed.value, SwapUncertain)
    assert await scalar(target.settings, "SELECT to_regclass('public.old_state')") is not None


async def test_an_uncertain_swap_keeps_maintenance_on_and_is_audited(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise SwapUncertain("restore.swap_broken")

    monkeypatch.setattr("app.ops.replace_steps.swap_database", broken)
    with pytest.raises(RestoreFailed) as failed:
        await replace_running(
            target.settings, archive, confirm=NAME, without_secrets=False,
            clock=SettableClock(AT), drain_seconds=0,
        )  # fmt: skip

    assert failed.value.code == "restore.swap_broken"
    assert await scalar(target.settings, ACTIVE) == 1, "maintenance ended"
    assert await scalar(target.settings, FAILED) == "restore.swap_broken"


async def test_a_replace_interrupted_after_the_commit_keeps_the_archives_state(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cancel comes after psql committed, before the exit was seen (F5)."""
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    run = swap._run

    async def committed_then_cancelled(*args: Any) -> None:
        await run(*args)
        raise asyncio.CancelledError

    monkeypatch.setattr(swap, "_run", committed_then_cancelled)
    with pytest.raises(RestoreFailed) as failed:
        await replace_running(
            target.settings, archive, confirm=NAME, without_secrets=False,
            clock=SettableClock(AT), drain_seconds=0,
        )  # fmt: skip

    assert failed.value.code == "restore.finish_failed"
    assert await marked(target.settings) == 0  # the archive's state
    assert await scalar(target.settings, ACTIVE) == 1  # not finished: maintenance on
    assert await scalar(target.settings, FAILED) is None  # nothing claims the old state
    assert await scalar(target.settings, COMMENT) is None  # the marker is gone again
