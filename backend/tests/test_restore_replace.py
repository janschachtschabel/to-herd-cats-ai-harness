"""Replacing a running installation with an archive (plan M9 task 12, decision 9):
the organisation's name confirms it, a safety archive of the present state comes
first, maintenance holds the installation still, one transaction swaps the database
(all or nothing), everyone is signed out, and maintenance ends. The running
installation: `tests/replace_helpers.py`."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.db import set_database
from app.modules.audit.models import AuditLog
from app.modules.backups.models import BackupRun
from app.modules.maintenance import repository as maintenance_sql
from app.ops.archive import read_sidecar
from app.ops.replace import replace_running
from app.ops.restore import RestoreFailed, RestoreRefused
from tests.factories import login
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.real_db import MakeRealClient, RealDb
from tests.replace_helpers import NAME, marked, rows, running, scalar
from tests.support.clock import SettableClock
from tests.test_restore_apply import _target_client
from tests.test_wiki_attachment_commit import PNG, _page_with


async def test_replace_takes_a_safety_archive_first(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    report = await replace_running(
        target.settings,
        archive,
        confirm=NAME,
        without_secrets=False,
        clock=SettableClock(AT),
        drain_seconds=0,
    )
    assert await marked(target.settings) == 0  # the archive's state
    safety = report.safety_archive
    assert safety.parent == target.settings.backup_dir and safety.exists()
    manifest, _ = read_sidecar(safety)
    # The present state, taken before maintenance began (no maintenance row yet).
    assert manifest.tables["user_group"] == read_sidecar(archive)[0].tables["user_group"] + 1
    assert manifest.tables["maintenance"] == 0
    # The safety archive stays listed in the replaced installation.
    runs = await rows(
        target.settings,
        select(BackupRun.trigger, BackupRun.state, BackupRun.archive).where(
            BackupRun.trigger == "pre_restore"
        ),
    )
    assert runs == [("pre_restore", "ok", safety.name)]
    assert not await scalar(target.settings, "SELECT count(*) FROM maintenance WHERE active")


async def test_replace_signs_everyone_out_and_audits(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, [attachment] = await _page_with(owner, ("a.png", PNG))
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    client, database = await _target_client(target)
    try:
        await login(client, real_db.owner_email)  # a session in the running installation
        assert (await client.get("/api/auth/me")).status_code == 200
        report = await replace_running(
            target.settings,
            archive,
            confirm=NAME,
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=0,
        )
        assert (await client.get("/api/auth/me")).status_code == 401
        client.cookies.clear()
        await login(client, real_db.owner_email)
        assert (await client.get("/api/auth/me")).status_code == 200
    finally:
        await client.aclose()
        set_database(real_db.database)
        await database.dispose()
    assert await scalar(target.settings, "SELECT count(*) FROM user_session") == 1  # fresh
    entries = await rows(
        target.settings,
        select(AuditLog.action, AuditLog.actor_type, AuditLog.details)
        .where(AuditLog.action.in_(["backup.restored", "maintenance.ended"]))
        .order_by(AuditLog.id),
    )
    assert [(a, t) for a, t, _ in entries] == [
        ("backup.restored", "system"),
        ("maintenance.ended", "system"),
    ]
    details = entries[0][2]
    assert details == {
        "archive": archive.name,
        "revision_from": report.restore.revision_from,
        "revision_to": report.restore.revision_to,
        "replaced": True,
        "safety_archive": report.safety_archive.name,
        "via": "cli",
    }
    assert attachment["sha256"] in "".join(target.files())


async def test_a_failed_replace_keeps_the_old_state(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    # A file only the archive has, so that the replace writes one.
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    await _page_with(owner, ("b.png", PNG + b"other"))
    archive = await make_archive(source_settings(tmp_path / "second", data_dir))
    before_tables = await target.tables()
    before_files = target.files()
    stay_on = maintenance_sql.stay_on_sql
    # An SQL error in the middle of the swap: after DROP SCHEMA and the archive's data.
    monkeypatch.setattr(
        "app.ops.replace_steps.stay_on_sql", lambda at: stay_on(at) + "SELECT 1 / 0;\n"
    )
    with pytest.raises(RestoreFailed) as failed:
        await replace_running(
            target.settings,
            archive,
            confirm=NAME,
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=0,
        )
    assert failed.value.code == "restore.swap_failed"
    assert await marked(target.settings) == 1
    assert target.files() == before_files
    after = await target.tables()
    # Only the bookkeeping of the attempt: the safety archive's run, maintenance on
    # and off, and the audit (`maintenance.started`, `backup.created`,
    # `maintenance.ended`, `backup.restore_failed`).
    assert after == before_tables | {
        "backup_run": before_tables["backup_run"] + 1,
        "maintenance": 1,
        "audit_log": before_tables["audit_log"] + 4,
    }
    assert not await scalar(target.settings, "SELECT count(*) FROM maintenance WHERE active")
    runs = await rows(
        target.settings,
        select(BackupRun.trigger, BackupRun.state).where(BackupRun.trigger == "pre_restore"),
    )
    assert runs == [("pre_restore", "ok")]  # the safety archive is good: kept for undo
    [entry] = await rows(
        target.settings,
        select(AuditLog.details).where(AuditLog.action == "backup.restore_failed"),
    )
    assert entry.details == {"archive": archive.name, "code": "restore.swap_failed", "via": "cli"}


async def test_replace_needs_the_organisations_name(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    before = await target.tables()
    with pytest.raises(RestoreRefused) as refused:
        await replace_running(
            target.settings,
            archive,
            confirm="Real org",
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=0,
        )
    assert refused.value.problems == ["restore.confirm_mismatch"]
    assert await target.tables() == before
    assert not target.settings.backup_dir.exists() or not any(
        target.settings.backup_dir.glob("*.tar")
    )
