"""Files behind one small protocol (spec 9, 12.4): `LocalStorage` (a directory) or
`S3Storage` (`storage_s3.py`, an S3-compatible store), chosen by `HERD_STORAGE`
(`get_storage`).

Keys are built by the application, never from user input (`attachments/<org_id>/
<sha256>`); both backends refuse any key that is not plain lower-case segments, so no
key can leave its root. A write names its size and SHA-256 up front and is checked
against them: content that does not match is refused (`StoredContentMismatch`) and
leaves nothing behind. A local write goes to a temporary file next to the target and
is renamed into place: a reader sees the whole file or none. A store that cannot be
reached answers 503 `storage.unavailable` (`StorageUnavailable`, its reason a fixed
code for the log).
"""

import asyncio
import hashlib
import os
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import Settings, get_settings
from app.core.errors import AppError

CHUNK = 64 * 1024
_KEY = re.compile(r"[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*")


class StorageKeyError(ValueError):
    """A key that is not plain lower-case segments (`..`, absolute, odd characters)."""


class StoredFileMissing(LookupError):
    """No file under the key."""


class StoredContentMismatch(ValueError):
    """The bytes of a write are not the size or SHA-256 it named; nothing was stored."""


class StorageUnavailable(AppError):
    """The store did not answer as it should (unreachable, refused, keys wrong)."""

    status_code = 503
    code = "storage.unavailable"

    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason


@dataclass(frozen=True)
class StoredFile:
    size: int
    sha256: str | None  # None: the store does not know it (`stored_sha256` reads it)


class Storage(Protocol):
    async def put(self, key: str, data: AsyncIterator[bytes], *, size: int, sha256: str) -> int:
        """Store the bytes under `key` (replacing what was there) if they are `size`
        bytes with this SHA-256, else `StoredContentMismatch`; returns how many."""
        ...

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """The bytes under `key`, in chunks; `StoredFileMissing` if there are none."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the file under `key`; nothing there is fine."""
        ...

    async def exists(self, key: str) -> bool:
        """Whether a file is stored under `key`."""
        ...

    async def stat(self, key: str) -> StoredFile | None:
        """Size and, where known, SHA-256 of the file under `key`; None if none."""
        ...

    def entries(self, prefix: str) -> AsyncIterator[tuple[str, int]]:
        """Every key under `prefix` (a key's leading segments) with its size."""
        ...


def valid_key(key: str) -> bool:
    return _KEY.fullmatch(key) is not None


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path_of(self, key: str) -> Path:
        if not valid_key(key):
            raise StorageKeyError("invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise StorageKeyError("storage key outside the root")
        return path

    async def put(self, key: str, data: AsyncIterator[bytes], *, size: int, sha256: str) -> int:
        path = self.path_of(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        part = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
        handle = await asyncio.to_thread(part.open, "xb")
        written, digest = 0, hashlib.sha256()
        try:
            async for chunk in data:
                written += len(chunk)
                if written > size:
                    raise StoredContentMismatch(key)
                digest.update(chunk)
                await asyncio.to_thread(handle.write, chunk)
            if written != size or digest.hexdigest() != sha256:
                raise StoredContentMismatch(key)
            await asyncio.to_thread(_sync_close, handle)
            await asyncio.to_thread(os.replace, part, path)
        except BaseException:
            handle.close()
            part.unlink(missing_ok=True)
            raise
        return written

    async def open(self, key: str) -> AsyncIterator[bytes]:
        path = self.path_of(key)
        try:
            handle = await asyncio.to_thread(path.open, "rb")
        except FileNotFoundError:
            raise StoredFileMissing(key) from None
        return _chunks(handle)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.path_of(key).unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self.path_of(key).is_file)

    async def stat(self, key: str) -> StoredFile | None:
        path = self.path_of(key)
        try:
            return await asyncio.to_thread(_stat_file, path)
        except (FileNotFoundError, IsADirectoryError):
            return None

    async def entries(self, prefix: str) -> AsyncIterator[tuple[str, int]]:
        top = self.path_of(prefix) if prefix else self.root
        found = await asyncio.to_thread(_walk, top, self.root)
        for entry in found:
            yield entry


def _stat_file(path: Path) -> StoredFile:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
        return StoredFile(handle.tell(), digest.hexdigest())


def _walk(top: Path, root: Path) -> list[tuple[str, int]]:
    """The files below `top` whose relative path is a key (no `.part` files, no
    links), sorted."""
    found: list[tuple[str, int]] = []
    for directory, _, names in os.walk(top):
        for name in names:
            path = Path(directory) / name
            key = path.relative_to(root).as_posix()
            if _KEY.fullmatch(key) and not path.is_symlink() and path.is_file():
                found.append((key, path.stat().st_size))
    return sorted(found)


async def stored_sha256(storage: Storage, key: str) -> str | None:
    """The SHA-256 of the file under `key` (read through if the store does not keep
    it); None if there is none."""
    info = await storage.stat(key)
    if info is None:
        return None
    if info.sha256 is not None:
        return info.sha256
    digest = hashlib.sha256()
    try:
        async for chunk in await storage.open(key):
            digest.update(chunk)
    except StoredFileMissing:
        return None
    return digest.hexdigest()


def _sync_close(handle: BinaryIO) -> None:
    handle.flush()
    os.fsync(handle.fileno())
    handle.close()


async def _chunks(handle: BinaryIO) -> AsyncIterator[bytes]:
    try:
        while chunk := await asyncio.to_thread(handle.read, CHUNK):
            yield chunk
    finally:
        handle.close()


def get_storage(settings: Settings | None = None) -> Storage:
    """The storage `HERD_STORAGE` names (the S3 one shares its connections per event
    loop)."""
    settings = settings or get_settings()
    if settings.storage == "s3":
        from app.core.storage_s3 import s3_storage  # noqa: PLC0415 (local needs no httpx)

        return s3_storage(settings)
    return LocalStorage(settings.data_dir)
