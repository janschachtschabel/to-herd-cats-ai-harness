"""The archives in HERD_BACKUP_DIR as the administration sees them (plan M9 task 13):
the backups' own (`herd-<UTC>-<version>.tar`) and those an owner uploaded
(`upload-<UTC>-<8 hex>.tar`). Nothing else in the directory is shown or served: a name
must match exactly, the file must be a regular file (never a link), and names never
come from a client except to pick one of these.

An upload streams into a hidden `.upload-*.part` file (mode 0600) next to the
archives, never into memory or /tmp, refused past `max_bytes` (`backup.upload_too_large`)
and when a part takes longer than HERD_BODY_READ_TIMEOUT_SECONDS. It is then read back
like a backup (`verify_archive`: format, members against the inner manifest); an
archive with any problem is removed and refused (`backup.archive_invalid` with the
codes). A good one gets its sidecar (manifest and SHA-256, so a later change shows up
as `archive.checksum`) and is renamed into place. A `.part` left by a dead process is
removed by the next upload once it is a day old.
"""

import asyncio
import hashlib
import os
import re
import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.core.errors import AppError, ValidationFailed
from app.core.uploads import arriving
from app.ops.archive import private_dir, sidecar_of, verify_archive, write_sidecar
from app.ops.restore_checks import inner_manifest

NAME = re.compile(r"(herd|upload)-(\d{8}T\d{6}Z)-[A-Za-z0-9][A-Za-z0-9._+-]{0,40}\.tar")
STAMP = "%Y%m%dT%H%M%SZ"
UPLOAD_PREFIX = "upload-"
UPLOAD_PART = re.compile(r"\.upload-.*\.part")
STALE_PART_SECONDS = 24 * 60 * 60
UPLOAD_SECONDS = 6 * 60 * 60  # a whole upload, however slow the line (2 GiB at 100 kB/s)


class UploadTooLarge(AppError):
    status_code = 413
    code = "backup.upload_too_large"


@dataclass(frozen=True)
class ArchiveFile:
    name: str
    size: int
    created_at: datetime  # from the name: when the backup was made or the upload came
    uploaded: bool
    path: Path


def _of(directory: Path, name: str) -> ArchiveFile | None:
    match = NAME.fullmatch(name)
    if match is None:
        return None
    path = directory / name
    try:
        info = path.lstat()
    except OSError:
        return None
    if not path.is_file() or path.is_symlink():
        return None
    created = datetime.strptime(match.group(2), STAMP).replace(tzinfo=UTC)
    return ArchiveFile(name, info.st_size, created, name.startswith(UPLOAD_PREFIX), path)


def find(directory: Path, name: str) -> ArchiveFile | None:
    """The archive of that name, or None (also for any name that is not one)."""
    return _of(directory, name)


def archive_files(directory: Path) -> list[ArchiveFile]:
    """Every archive, newest first (by the time in the name, then the name)."""
    try:
        names = [entry.name for entry in os.scandir(directory)]
    except OSError:
        return []
    found = [a for name in names if (a := _of(directory, name)) is not None]
    return sorted(found, key=lambda a: (a.created_at, a.name), reverse=True)


def page_after(files: list[ArchiveFile], after: str | None, limit: int) -> list[ArchiveFile]:
    """Up to `limit` + 1 of `files` (sorted as `archive_files`) after the name `after`."""
    if after is not None:
        last = NAME.fullmatch(after)
        if last is None:
            raise ValidationFailed("Invalid cursor", code="validation_failed")
        key = (datetime.strptime(last.group(2), STAMP).replace(tzinfo=UTC), after)
        files = [a for a in files if (a.created_at, a.name) < key]
    return files[: limit + 1]


class ArchiveInvalid(Exception):  # noqa: N818 (a verdict on the upload)
    def __init__(self, problems: list[str]) -> None:
        super().__init__(", ".join(problems))
        self.problems = problems


async def receive(
    directory: Path,
    stream: AsyncIterator[bytes],
    *,
    max_bytes: int,
    read_timeout: float,
    at: datetime,
) -> ArchiveFile:
    """The uploaded archive, checked and in place (see the module's text)."""
    private_dir(directory)
    _remove_stale_parts(directory)
    name = f"{UPLOAD_PREFIX}{at.astimezone(UTC):{STAMP}}-{secrets.token_hex(4)}.tar"
    path = directory / name
    part = directory / f".{name}.part"
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        archive_sha256 = await _write(fd, stream, max_bytes, read_timeout)
        problems = await asyncio.to_thread(verify_archive, part)
        if problems:
            raise ArchiveInvalid(problems)
        manifest = await asyncio.to_thread(inner_manifest, part)
        os.replace(part, path)
        write_sidecar(path, manifest.to_json(), archive_sha256)
    except BaseException:
        part.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        sidecar_of(path).unlink(missing_ok=True)
        raise
    found = _of(directory, name)
    assert found is not None  # just written
    return found


async def _write(fd: int, stream: AsyncIterator[bytes], max_bytes: int, read_timeout: float) -> str:
    digest = hashlib.sha256()
    size = 0
    with os.fdopen(fd, "wb") as out:
        async for chunk in arriving(stream, read_timeout, UPLOAD_SECONDS):
            size += len(chunk)
            if size > max_bytes:
                raise UploadTooLarge()
            digest.update(chunk)
            await asyncio.to_thread(out.write, chunk)
        await asyncio.to_thread(_sync, out)
    return digest.hexdigest()


def _sync(out: BinaryIO) -> None:
    out.flush()
    os.fsync(out.fileno())


def _remove_stale_parts(directory: Path) -> None:
    limit = time.time() - STALE_PART_SECONDS
    for entry in os.scandir(directory):
        if UPLOAD_PART.fullmatch(entry.name) and entry.is_file(follow_symlinks=False):
            if entry.stat(follow_symlinks=False).st_mtime < limit:
                Path(entry.path).unlink(missing_ok=True)
