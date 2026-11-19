"""Moving attachments between storages (plan M9 decision 18) and checking one.

`copy_files` lists both sides under `attachments` and copies each file the target
does not hold with the same size: idempotent per key (keys are content-addressed, the
same key holds the same bytes), so it can run while the app writes and once more after
it stopped. Each file is read once into a spool (`HERD_DATA_DIR/tmp`), hashed, and
written with its size and SHA-256, so the target checks it. A file that vanished from
the source meanwhile (its tombstone's grace ended) counts as `gone`.

`check_storage` writes, reads back and removes a probe under `probe/`.
"""

import asyncio
import hashlib
import tempfile
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from app.core.storage import CHUNK, Storage, StoredFileMissing

PREFIX = "attachments"
_MEMORY = 1024 * 1024
PROBE = b"to-herd-cats-ai storage check\n"


class CheckFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CopyReport:
    copied: int
    present: int
    gone: int
    bytes: int


async def copy_files(source: Storage, target: Storage, spool_dir: Path) -> CopyReport:
    there = {key: size async for key, size in target.entries(PREFIX)}
    copied = present = gone = moved = 0
    await asyncio.to_thread(spool_dir.mkdir, parents=True, exist_ok=True)
    async for key, size in source.entries(PREFIX):
        if there.get(key) == size:
            present += 1
            continue
        with tempfile.SpooledTemporaryFile(max_size=_MEMORY, dir=str(spool_dir)) as spool:
            try:
                length, sha256 = await _spool(source, key, spool)
            except StoredFileMissing:
                gone += 1
                continue
            await target.put(key, _chunks(spool), size=length, sha256=sha256)
        copied += 1
        moved += length
    return CopyReport(copied, present, gone, moved)


async def _spool(source: Storage, key: str, spool: IO[bytes]) -> tuple[int, str]:
    digest, length = hashlib.sha256(), 0
    async for chunk in await source.open(key):
        digest.update(chunk)
        length += len(chunk)
        await asyncio.to_thread(spool.write, chunk)
    await asyncio.to_thread(spool.seek, 0)
    return length, digest.hexdigest()


async def _chunks(spool: IO[bytes]) -> AsyncIterator[bytes]:
    while chunk := await asyncio.to_thread(spool.read, CHUNK):
        yield chunk


async def _probe_chunks() -> AsyncIterator[bytes]:
    yield PROBE


async def check_storage(storage: Storage) -> None:
    """Write, read back and remove a probe; `CheckFailed` when the bytes differ."""
    key = f"probe/{uuid.uuid4().hex}"
    await storage.put(
        key, _probe_chunks(), size=len(PROBE), sha256=hashlib.sha256(PROBE).hexdigest()
    )
    try:
        read = b"".join([chunk async for chunk in await storage.open(key)])
        if read != PROBE:
            raise CheckFailed("storage.probe_differs")
    finally:
        await storage.delete(key)
    if await storage.exists(key):
        raise CheckFailed("storage.probe_stays")
