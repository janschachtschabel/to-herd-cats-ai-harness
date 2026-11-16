"""Making one backup (plan M9 decisions 2 to 5 and 11).

0. The database must stand at the code's head (`backup.no_schema`,
   `backup.schema_behind`, `backup.schema_ahead`; unreachable:
   `backup.database_unavailable`), and no other backup may run: a backup holds the
   backup lock on a connection of its own while it runs (`backup.already_running`).
   These refusals write no `backup_run` row.
1. Rows still `running` belong to backups whose process died (killed by the job's time
   limit, say): holding the lock, the backup marks them `interrupted` (as the worker's
   due loop and a restore do) and removes the hidden `.herd-*.part` files such a backup
   left in the backups directory (`remove_leftovers`). Its own `running` row is
   committed first, so a backup that dies midway is visible.
2. In one exported snapshot: the figures (`snapshot.py`) and `pg_dump -Fc --snapshot`
   into a hidden scratch file next to the archive (`.<name>.db.dump.part`, mode 0600),
   never into /tmp; it is removed once it is in the archive or the backup failed.
3. The snapshot's attachment files are copied from the storage, local or S3
   (`HERD_STORAGE`; a deleted file stays for its tombstone's grace,
   `core/storage_tombstones.py`), then the manifest (naming the storage).
4. The archive is read back (`verify_archive`); only a good one makes the run `ok`.

Any failure removes what was written and makes the run `failed` with a code
(`backup.no_organization`, `backup.no_schema`, `backup.tool_missing`,
`backup.tools_too_old`, `backup.dump_failed`, `backup.file_missing`,
`backup.storage_unavailable` (the object store did not answer), `backup.io`,
`backup.verify_failed`, `backup.failed`). Nothing of the content is logged; a success
is audited as `backup.created` by `system` with the trigger as `via`.
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.core.migrations import SchemaState, schema_state
from app.core.secrets import key_id
from app.core.storage import Storage, StorageUnavailable, StoredFileMissing, get_storage
from app.modules.audit.recorder import record_system
from app.modules.backups.models import BackupState, BackupTrigger
from app.modules.backups.repository import (
    BackupRunRepository,
    hold_backup_lock,
    release_backup_lock,
)
from app.ops.archive import (
    DUMP_MEMBER,
    FILES_PREFIX,
    ArchiveError,
    ArchiveWriter,
    private_dir,
    sidecar_of,
    verify_archive,
)
from app.ops.manifest import CREATED_AT_FORMAT, FORMAT, Manifest
from app.ops.pgtools import ToolFailed, dump, tool_version
from app.ops.snapshot import NoSchema, Snapshot, open_snapshot
from app.version import app_version

logger = logging.getLogger(__name__)

ARCHIVE_PREFIX = "herd-"
PART_SUFFIX = ".part"
SCHEMA_CODES = {
    SchemaState.NONE: "backup.no_schema",
    SchemaState.BEHIND: "backup.schema_behind",
    SchemaState.AHEAD: "backup.schema_ahead",
}


class BackupFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BackupOutcome:
    run_id: uuid.UUID | None
    archive: Path | None
    state: BackupState
    error_code: str | None


def archive_name(at: datetime, version: str) -> str:
    return f"{ARCHIVE_PREFIX}{at.astimezone(UTC):%Y%m%dT%H%M%SZ}-{version}.tar"


async def create_backup(
    settings: Settings, *, trigger: BackupTrigger, clock: Clock
) -> BackupOutcome:
    engine = make_engine(settings.database())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        return await _create(settings, engine, sessions, trigger, clock)
    finally:
        await engine.dispose()


def _refused(code: str) -> BackupOutcome:
    logger.warning("backup.refused", extra={"code": code})
    return BackupOutcome(None, None, BackupState.FAILED, code)


async def _create(
    settings: Settings,
    engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    trigger: BackupTrigger,
    clock: Clock,
) -> BackupOutcome:
    try:
        schema = await schema_state(engine)
    except (OSError, SQLAlchemyError):
        return _refused("backup.database_unavailable")
    if schema != SchemaState.HEAD:
        return _refused(SCHEMA_CODES[schema])
    async with engine.connect() as holder:
        if not await hold_backup_lock(holder):
            return _refused("backup.already_running")
        try:
            return await _locked(settings, engine, sessions, trigger, clock)
        finally:
            await _release(holder)


async def _release(holder: AsyncConnection) -> None:
    """Release the backup lock. A holder whose connection is gone lost its session
    lock with it: logged with a code, and the backup's outcome stands."""
    try:
        await release_backup_lock(holder)
    except (OSError, SQLAlchemyError) as exc:
        logger.warning(
            "backup.lock_release_failed",
            extra={"code": "backup.lock_lost", "error": type(exc).__name__},
        )


async def _locked(
    settings: Settings,
    engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    trigger: BackupTrigger,
    clock: Clock,
) -> BackupOutcome:
    started = clock.now()
    async with sessions() as session, session.begin():
        runs = BackupRunRepository(session)
        org_id = await runs.installation_org()
        if org_id is None:
            return BackupOutcome(None, None, BackupState.FAILED, "backup.no_organization")
        if dead := await runs.interrupt_running(started):
            logger.warning("backup.interrupted_found", extra={"count": dead})
        if left := remove_leftovers(settings.backup_dir):
            logger.warning("backup.leftovers_removed", extra={"count": left})
        run_id = (await runs.start(org_id, trigger, started)).id
    path = settings.backup_dir / archive_name(started, app_version())
    written = False
    try:
        archive_sha256 = await _write(settings, engine, path, started)
        written = True
        if verify_archive(path):
            raise BackupFailed("backup.verify_failed")
    except Exception as exc:
        code = _code_of(exc)
        logger.warning("backup.failed", extra={"code": code, "error": type(exc).__name__})
        if written:  # never an archive of the same name that was there before
            _remove(path)
        async with sessions() as session, session.begin():
            await BackupRunRepository(session).finish(
                run_id, state=BackupState.FAILED, at=clock.now(), error_code=code
            )
        return BackupOutcome(run_id, None, BackupState.FAILED, code)
    size = path.stat().st_size
    async with sessions() as session, session.begin():
        await BackupRunRepository(session).finish(
            run_id,
            state=BackupState.OK,
            at=clock.now(),
            archive=path.name,
            size=size,
            archive_sha256=archive_sha256,
        )
        details = {"archive": path.name, "bytes": size, "via": trigger.value}
        await record_system(session, org_id, "backup.created", "backup_run", run_id, details)
    logger.info("backup.created", extra={"run_id": str(run_id), "bytes": size})
    return BackupOutcome(run_id, path, BackupState.OK, None)


async def write_archive(settings: Settings, path: Path, at: datetime) -> str:
    """An archive of the settings' database at `path`, without a `backup_run` row
    (`create_backup` records one); the archive's SHA-256."""
    engine = make_engine(settings.database())
    try:
        return await _write(settings, engine, path, at)
    finally:
        await engine.dispose()


async def _write(settings: Settings, engine: AsyncEngine, path: Path, at: datetime) -> str:
    private_dir(path.parent)
    pg_dump_version = tool_version("pg_dump")
    storage = get_storage(settings)
    dump_file = path.with_name(f".{path.name.removesuffix('.tar')}.{DUMP_MEMBER}{PART_SUFFIX}")
    os.close(os.open(dump_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    try:
        async with open_snapshot(engine) as snapshot:
            if int(pg_dump_version.split(".")[0]) < snapshot.server_major:
                raise BackupFailed("backup.tools_too_old")
            await dump(settings, snapshot.snapshot_id, dump_file)
        writer = ArchiveWriter(path)
        try:
            await writer.add_file(DUMP_MEMBER, dump_file)
            dump_file.unlink()
            await _add_files(writer, storage, snapshot)
            return await writer.finish(_manifest(settings, snapshot, pg_dump_version, at))
        except BaseException:
            writer.abort()
            raise
    finally:
        dump_file.unlink(missing_ok=True)


def remove_leftovers(directory: Path) -> int:
    """Remove the hidden `.herd-*.part` files of backups that died midway (archive,
    sidecar and scratch dump); the number removed. Only while holding the backup lock:
    then no other backup is writing one."""
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.glob(f".{ARCHIVE_PREFIX}*{PART_SUFFIX}"):
        if path.is_file() and not path.is_symlink():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


async def _add_files(writer: ArchiveWriter, storage: Storage, snapshot: Snapshot) -> None:
    for file in snapshot.files:
        try:
            chunks = await storage.open(file.key)
        except StoredFileMissing:
            raise BackupFailed("backup.file_missing") from None
        await writer.add_stream(FILES_PREFIX + file.key, file.size, chunks)


def _manifest(
    settings: Settings, snapshot: Snapshot, pg_dump_version: str, at: datetime
) -> Manifest:
    secret = settings.secret_key
    return Manifest(
        format=FORMAT,
        app_version=app_version(),
        alembic_revision=snapshot.alembic_revision,
        created_at=at.astimezone(UTC).strftime(CREATED_AT_FORMAT),
        server_major=snapshot.server_major,
        pg_dump_version=pg_dump_version,
        storage=settings.storage,
        tables=snapshot.tables,
        files={"count": len(snapshot.files), "bytes": sum(f.size for f in snapshot.files)},
        members={},
        key_id=key_id(secret.get_secret_value()) if secret is not None else None,
        enc_values=snapshot.enc_values,
        env_refs=snapshot.env_refs,
    )


def _code_of(exc: Exception) -> str:
    if isinstance(exc, BackupFailed | ToolFailed | ArchiveError):
        return exc.code
    if isinstance(exc, NoSchema):
        return "backup.no_schema"
    if isinstance(exc, StorageUnavailable):
        return "backup.storage_unavailable"
    if isinstance(exc, OSError):
        return "backup.io"
    return "backup.failed"


def _remove(path: Path) -> None:
    path.unlink(missing_ok=True)
    sidecar_of(path).unlink(missing_ok=True)
