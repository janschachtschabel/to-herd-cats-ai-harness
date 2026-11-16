"""Restoring an archive into an empty installation (plan M9 decision 6).

Under the schema lock (`schema_lock.py`, held from the check to the end) and the
backup lock (refused with `restore.backup_running` while a backup runs; no backup
starts until the restore is over): the checks
(`restore_checks.py`; with `without_secrets` the key problems are let pass), the files
(each checked against the manifest while written; keys already here have the same
content), the database with `pg_restore --single-transaction` (files added for it are
removed again if it fails), `alembic upgrade head` when the archive is older, and
`finish_restore`. The dump goes from the archive straight into pg_restore's stdin, so
a restore needs no scratch space. A refused restore changes nothing (`RestoreRefused`
with the codes); a failed one raises `RestoreFailed` with a code.
"""

import asyncio
import hashlib
import tarfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.core.migrations import upgrade_head
from app.core.storage import LocalStorage
from app.modules.backups.repository import hold_backup_lock, release_backup_lock
from app.ops.archive import CHUNK, DUMP_MEMBER, FILES_PREFIX, PREFIX
from app.ops.manifest import Manifest
from app.ops.pgtools import ToolFailed, restore
from app.ops.restore_after import finish_restore
from app.ops.restore_checks import KEY_PROBLEMS, check_on
from app.ops.schema_lock import schema_lock
from app.ops.snapshot import row_counts


class RestoreRefused(Exception):  # noqa: N818 (a verdict)
    def __init__(self, problems: list[str]) -> None:
        super().__init__(", ".join(problems))
        self.problems = problems


class RestoreFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RestoreReport:
    revision_from: str
    revision_to: str
    tables: dict[str, int]
    files: int


async def restore_into_empty(
    settings: Settings, archive: Path, *, without_secrets: bool, clock: Clock
) -> RestoreReport:
    engine = make_engine(settings.database())
    try:
        async with engine.connect() as conn, schema_lock(conn):
            if not await hold_backup_lock(conn):
                raise RestoreRefused(["restore.backup_running"])
            try:
                check = await check_on(conn, settings, archive)
                await conn.commit()
                problems = [
                    p for p in check.problems if not (without_secrets and p in KEY_PROBLEMS)
                ]
                if problems or check.manifest is None:
                    raise RestoreRefused(problems)
                return await _apply(conn, settings, archive, check.manifest, clock)
            finally:
                await release_backup_lock(conn)
    finally:
        await engine.dispose()


async def _apply(
    conn: AsyncConnection, settings: Settings, archive: Path, manifest: Manifest, clock: Clock
) -> RestoreReport:
    storage = LocalStorage(settings.data_dir)
    added = await _restore_files(storage, archive, manifest)
    try:
        await _restore_database(settings, archive)
    except BaseException:
        for key in added:
            await storage.delete(key)
        raise
    await conn.run_sync(upgrade_head)
    await conn.commit()
    revision_to = ",".join(sorted(await _heads(conn)))
    async with AsyncSession(bind=conn, expire_on_commit=False) as session:
        await finish_restore(
            session,
            archive_name=archive.name,
            archive_created_at=manifest.created(),
            revision_from=manifest.alembic_revision,
            revision_to=revision_to,
            clock=clock,
        )
        await session.commit()
    tables = await row_counts(conn)
    await conn.commit()
    files = sum(1 for name in manifest.members if name.startswith(FILES_PREFIX))
    return RestoreReport(manifest.alembic_revision, revision_to, tables, files)


async def _heads(conn: AsyncConnection) -> list[str]:
    from sqlalchemy import text  # noqa: PLC0415

    return list((await conn.scalars(text("SELECT version_num FROM alembic_version"))).all())


async def _restore_files(storage: LocalStorage, archive: Path, manifest: Manifest) -> list[str]:
    """Write the archive's files that are not here yet; the keys written."""
    added: list[str] = []
    try:
        with tarfile.open(archive, "r:") as tar:
            for name, member in manifest.members.items():
                if not name.startswith(FILES_PREFIX):
                    continue
                key = name.removeprefix(FILES_PREFIX)
                if await storage.exists(key):
                    continue  # the same content (checked)
                handle = tar.extractfile(PREFIX + name)
                if handle is None:
                    raise RestoreFailed("archive.member_missing")
                digest = hashlib.sha256()
                added.append(key)
                await storage.put(key, _chunks(handle, digest))
                if digest.hexdigest() != member["sha256"]:
                    raise RestoreFailed("archive.member_checksum")
    except BaseException:
        for key in added:
            await storage.delete(key)
        raise
    return added


async def _restore_database(settings: Settings, archive: Path) -> None:
    """The archive's dump straight from the tar member into pg_restore: no scratch
    file (no /tmp, no second copy on disk). An archive that changed after the checks
    (a member cut off, the file gone) fails with an `archive.*` code; pg_restore
    never commits half of a dump."""
    try:
        with tarfile.open(archive, "r:") as tar:
            handle = tar.extractfile(PREFIX + DUMP_MEMBER)
            if handle is None:
                raise RestoreFailed("archive.member_missing")
            await restore(settings, _read(handle))
    except ToolFailed as failed:
        raise RestoreFailed(failed.code) from None
    except KeyError:
        raise RestoreFailed("archive.member_missing") from None
    except (tarfile.TarError, EOFError):
        raise RestoreFailed("archive.truncated") from None
    except OSError:
        raise RestoreFailed("archive.unreadable") from None


async def _read(handle: IO[bytes]) -> AsyncIterator[bytes]:
    while chunk := await asyncio.to_thread(handle.read, CHUNK):
        yield chunk


async def _chunks(handle: IO[bytes], digest: "hashlib._Hash") -> AsyncIterator[bytes]:
    while chunk := await asyncio.to_thread(handle.read, CHUNK):
        digest.update(chunk)
        yield chunk
