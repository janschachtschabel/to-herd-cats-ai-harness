"""Replacing a running installation with an archive (plan M9 decision 9).

Under the schema lock (`schema_lock.py`, held throughout: no migration and no other
restore in between):

1. The checks of `restore_checks.py` except "empty", and the organisation's exact
   name as confirmation (`restore.confirm_mismatch`). A refusal changes nothing.
2. A safety archive of the present state (`backup_run` with trigger `pre_restore`);
   without one, nothing goes on (`restore.safety_backup_failed`). Then the backup lock
   for the rest, so no backup reads the database while it is swapped.
3. Maintenance on (`maintenance.started`): the API answers 503 and the worker's loops
   pause, in every process within POLL_SECONDS (`modules/maintenance/cache.py`); then
   DRAIN_SECONDS for requests and steps under way to end.
4. The archive's files that are not here yet, in the configured storage (local or S3,
   `HERD_STORAGE`; content-addressed: present keys hold the same content), then the
   database in one transaction (`swap.py`: only our schema's entries of the dump),
   which also leaves maintenance on in the restored state. What follows a failure
   depends on the state the database says it holds (`replace_steps.py`):
   rolled back (anything failing here, the drain included: a cancel or Ctrl-C in
   it): the old state is whole, the files written are removed, maintenance ends,
   `backup.restore_failed` is audited (the safety run stays `ok`: its archive is good)
   and `RestoreFailed` carries the code; committed after all (a cancel once COMMIT was
   sent): `restore.finish_failed` as in point 5, the archive's files stay; neither
   (`restore.swap_broken`, `restore.swap_unknown`): maintenance stays on, nothing
   claims the old state.
5. In the restored database: `alembic upgrade head` with maintenance kept on in the
   same transaction (an older archive has no maintenance table before it), then
   `finish_restore` (everyone signed out, `backup.restored` with `replaced`, the
   safety archive and `via`), the safety run recorded here too, tombstones for the
   files only the old state used (`core/storage_tombstones.py`: they go after the
   grace, unless used again), and maintenance off.
   If a step here fails, maintenance stays on (`restore.finish_failed`): the database
   holds the archive, not yet ready to serve; `docs/SICHERUNG.md` says what to do.

`via` names who started it in the audit (`cli`, or `admin` for an owner in the
administration, `modules/backups/replacing.py`); with `wait` false a schema lock held
elsewhere (another restore, a migration) refuses at once (`restore.already_running`).
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.core.migrations import upgrade_head
from app.core.storage import Storage, get_storage
from app.core.storage_tombstones import bury
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.backups.repository import (
    BackupRunRepository,
    hold_backup_lock,
    release_backup_lock,
)
from app.modules.maintenance.models import MaintenanceReason
from app.modules.maintenance.repository import stay_on
from app.modules.maintenance.service import MaintenanceService
from app.ops.archive import FILES_PREFIX, read_sidecar
from app.ops.backup import create_backup
from app.ops.manifest import Manifest
from app.ops.replace_steps import Plan, failed, swap, uncertain
from app.ops.restore import (
    RestoreFailed,
    RestoreRefused,
    RestoreReport,
    heads,
    remove_files,
    restore_files,
)
from app.ops.restore_after import finish_restore
from app.ops.restore_checks import KEY_PROBLEMS, check_on
from app.ops.schema_lock import SchemaLockBusy, schema_lock
from app.ops.snapshot import row_counts
from app.ops.swap import SwapCommitted, SwapUncertain

logger = logging.getLogger(__name__)

DRAIN_SECONDS = 10.0
VIA = "cli"


@dataclass(frozen=True)
class ReplaceReport:
    restore: RestoreReport
    safety_archive: Path


async def replace_running(
    settings: Settings,
    archive: Path,
    *,
    confirm: str,
    without_secrets: bool,
    clock: Clock,
    drain_seconds: float | None = None,
    via: str = VIA,
    wait: bool = True,
) -> ReplaceReport:
    engine = make_engine(settings.migrate_database(), settings=settings)
    try:
        async with engine.connect() as conn:
            try:
                async with schema_lock(conn, wait=wait):
                    return await _locked(
                        conn, settings, archive, confirm, without_secrets, clock, drain_seconds, via
                    )
            except SchemaLockBusy:
                raise RestoreRefused(["restore.already_running"]) from None
    finally:
        await engine.dispose()


async def _locked(
    conn: AsyncConnection,
    settings: Settings,
    archive: Path,
    confirm: str,
    without_secrets: bool,
    clock: Clock,
    drain_seconds: float | None,
    via: str,
) -> ReplaceReport:
    check = await check_on(conn, settings, archive, into_empty=False)
    async with AsyncSession(bind=conn) as session:
        installation = await BackupRunRepository(session).installation()
    await conn.commit()
    problems = [p for p in check.problems if not (without_secrets and p in KEY_PROBLEMS)]
    if installation is None or installation[1] != confirm:
        problems.append("restore.confirm_mismatch")
    if problems or check.manifest is None or installation is None:
        raise RestoreRefused(problems)
    plan = Plan(settings, archive, check.manifest, installation[0], clock, via)
    safety = await _safety_archive(conn, plan)
    if not await hold_backup_lock(conn):
        await conn.commit()
        raise RestoreRefused(["backup.already_running"])
    await conn.commit()
    try:
        drain = DRAIN_SECONDS if drain_seconds is None else drain_seconds
        report = await _replace(conn, plan, safety, drain)
    finally:
        await release_backup_lock(conn)
        await conn.commit()
    return ReplaceReport(report, settings.backup_dir / (safety.archive or ""))


async def _safety_archive(conn: AsyncConnection, plan: Plan) -> BackupRun:
    outcome = await create_backup(
        plan.settings, trigger=BackupTrigger.PRE_RESTORE, clock=plan.clock
    )
    run = None
    if outcome.state == BackupState.OK and outcome.run_id is not None:
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            run = await BackupRunRepository(session).get(outcome.run_id)
        await conn.commit()
    if run is None or run.archive is None:
        raise RestoreRefused([f"restore.safety_backup_failed:{outcome.error_code}"])
    return run


async def _replace(
    conn: AsyncConnection, plan: Plan, safety: BackupRun, drain: float
) -> RestoreReport:
    async with AsyncSession(bind=conn) as session:
        await MaintenanceService(session).begin(
            plan.org_id, MaintenanceReason.RESTORE, plan.clock.now(), via=plan.via
        )
        await session.commit()
    storage: Storage | None = None
    added: list[str] = []
    try:  # from here on, whatever ends the replace ends maintenance (review M9b F4)
        await asyncio.sleep(drain)  # requests and steps under way end; the caches follow
        storage = get_storage(plan.settings)  # local or S3 (`HERD_STORAGE`)
        added = await restore_files(storage, plan.archive, plan.manifest)
        await swap(plan)
    except SwapCommitted as exc:  # interrupted once the swap had committed (F5)
        raise RestoreFailed(exc.code) from exc  # the archive's files stay: it uses them
    except SwapUncertain as exc:  # the old state may be gone: maintenance stays on
        await uncertain(plan, exc.code)
        raise RestoreFailed(exc.code) from exc
    except BaseException as exc:  # the swap rolled back (or never began): the old state
        if storage is not None:
            await remove_files(storage, added)
        code = exc.code if isinstance(exc, RestoreFailed) else "restore.failed"
        await failed(conn, plan, code)
        if isinstance(exc, RestoreFailed) or not isinstance(exc, Exception):
            raise  # interrupted (a signal, a cancel): as it came
        raise RestoreFailed(code) from exc
    try:
        return await _finish(conn, plan, safety)
    except Exception as exc:
        raise RestoreFailed("restore.finish_failed") from exc


async def _finish(conn: AsyncConnection, plan: Plan, safety: BackupRun) -> RestoreReport:
    await conn.run_sync(upgrade_head)
    await stay_on(conn, plan.clock.now())  # the same transaction as the migration
    await conn.commit()
    revision_to = ",".join(sorted(await heads(conn)))
    await conn.commit()
    async with AsyncSession(bind=conn, expire_on_commit=False) as session:
        await finish_restore(
            session,
            archive_name=plan.archive.name,
            archive_created_at=plan.manifest.created(),
            revision_from=plan.manifest.alembic_revision,
            revision_to=revision_to,
            clock=plan.clock,
            replaced={"replaced": True, "safety_archive": safety.archive, "via": plan.via},
        )
        runs = BackupRunRepository(session)
        installation = await runs.installation()
        if installation is not None:
            await runs.copy_finished(installation[0], safety)
            await bury(session, installation[0], _only_old_files(plan, safety))
        await MaintenanceService(session).end_all(via=plan.via)
        await session.commit()
    tables = await row_counts(conn)
    await conn.commit()
    files = sum(1 for name in plan.manifest.members if name.startswith(FILES_PREFIX))
    return RestoreReport(plan.manifest.alembic_revision, revision_to, tables, files)


def _only_old_files(plan: Plan, safety: BackupRun) -> set[str]:
    """The files the replaced state had and the archive has not."""
    old, _ = read_sidecar(plan.settings.backup_dir / (safety.archive or ""))
    return _file_keys(old) - _file_keys(plan.manifest)


def _file_keys(manifest: Manifest) -> set[str]:
    return {n.removeprefix(FILES_PREFIX) for n in manifest.members if n.startswith(FILES_PREFIX)}
