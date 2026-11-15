"""Files behind one small protocol (spec 9, 12.4): attachments today, an S3 backend
behind the same protocol in M9.

Keys are built by the application, never from user input (`attachments/<org_id>/
<sha256>`); `LocalStorage` still refuses any key that is not plain lower-case
segments, so no key can leave its root. A write goes to a temporary file next to the
target and is renamed into place: a reader sees the whole file or none.
"""

import asyncio
import os
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import get_settings

CHUNK = 64 * 1024
_KEY = re.compile(r"[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*")


class StorageKeyError(ValueError):
    """A key that is not plain lower-case segments (`..`, absolute, odd characters)."""


class StoredFileMissing(LookupError):
    """No file under the key."""


class Storage(Protocol):
    async def put(self, key: str, data: AsyncIterator[bytes]) -> int:
        """Store the bytes under `key` (replacing what was there); returns how many."""
        ...

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """The bytes under `key`, in chunks; `StoredFileMissing` if there are none."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the file under `key`; nothing there is fine."""
        ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path_of(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise StorageKeyError("invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise StorageKeyError("storage key outside the root")
        return path

    async def put(self, key: str, data: AsyncIterator[bytes]) -> int:
        path = self.path_of(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        part = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
        handle = await asyncio.to_thread(part.open, "xb")
        written = 0
        try:
            async for chunk in data:
                await asyncio.to_thread(handle.write, chunk)
                written += len(chunk)
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


def get_storage() -> Storage:
    return LocalStorage(get_settings().data_dir)
