"""Replacing a running installation (plan M9 task 12): the command line, a dump that
ends early (nothing commits) and an archive of the release before maintenance (no
table yet: maintenance stays on through the swap and the migration)."""

from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.db import make_engine
from app.core.migrations import alembic_config
from app.ops.archive import read_chunks, read_sidecar
from app.ops.backup import write_archive
from app.ops.cli import run
from app.ops.replace import replace_running
from app.ops.restore import RestoreFailed
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.replace_helpers import NAME, marked, printed, running, scalar
from tests.support.clock import SettableClock
from tests.test_restore_apply import _scratch, _upgrade_to


async def test_the_command_line_replaces_with_the_name(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.ops.replace.DRAIN_SECONDS", 0)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    clock = SettableClock(AT)
    argv = ["restore", "apply", str(archive), "--replace"]
    assert await run(argv, target.settings, clock) == 1
    assert printed(capsys) == "restore.confirm_missing"
    assert await marked(target.settings) == 1
    assert await run([*argv, "--confirm", NAME], target.settings, clock) == 0
    out = printed(capsys)
    assert out.startswith(f"replaced by {archive.name}: revision ")
    assert "safety archive herd-" in out
    assert await marked(target.settings) == 0
    # Into an empty installation only without --replace, as before.
    assert await run(argv[:3], target.settings, clock) == 1
    assert printed(capsys) == "restore.target_not_empty"


async def test_a_cut_off_dump_commits_nothing(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pg_restore fails on a dump that ends early, after psql has had part of the
    script: no COMMIT is sent, psql is ended, the transaction rolls back."""
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    whole = read_chunks
    # All but the end: the schema and most data are through to psql already.
    keep = read_sidecar(archive)[0].members["db.dump"]["size"] - 4096

    async def cut(handle):  # type: ignore[no-untyped-def]
        sent = 0
        async for chunk in whole(handle):
            yield chunk[: keep - sent]
            sent += len(chunk)
            if sent >= keep:
                return

    monkeypatch.setattr("app.ops.replace_steps.read_chunks", cut)
    with pytest.raises(RestoreFailed) as failed:
        await replace_running(
            target.settings,
            archive,
            confirm=NAME,
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=0,
        )
    assert failed.value.code == "restore.pg_restore_failed"
    assert await marked(target.settings) == 1
    assert not await scalar(target.settings, "SELECT count(*) FROM maintenance WHERE active")


async def test_an_older_archive_replaces_and_is_migrated(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    """An archive of the release before maintenance (no table yet): maintenance stays
    on through the swap (the processes keep what they knew) and the migration."""
    script = ScriptDirectory.from_config(alembic_config())
    (head,) = script.get_heads()
    older = script.get_revision(head).down_revision
    assert isinstance(older, str)
    await running(target, await make_archive(source_settings(tmp_path, data_dir)))
    async with _scratch(target, "older") as url:
        engine = make_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: _upgrade_to(c, older))
            await conn.execute(
                text(f"INSERT INTO organization (id, name) VALUES (gen_random_uuid(), '{NAME}')")
            )
        await engine.dispose()
        archive = tmp_path / "older.tar"
        settings = source_settings(tmp_path, data_dir).model_copy(update={"database_url": url})
        await write_archive(settings, archive, AT)
    report = await replace_running(
        target.settings,
        archive,
        confirm=NAME,
        without_secrets=False,
        clock=SettableClock(AT),
        drain_seconds=0,
    )
    assert (report.restore.revision_from, report.restore.revision_to) == (older, head)
    assert await marked(target.settings) == 0
    assert await scalar(target.settings, "SELECT count(*) FROM maintenance") == 1
    assert not await scalar(target.settings, "SELECT count(*) FROM maintenance WHERE active")
