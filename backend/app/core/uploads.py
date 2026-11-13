"""Reading an uploaded body once, with a size limit: kept in memory up to 1 MiB, in a
temporary file beyond, hashed (SHA-256) and checked for UTF-8 on the way. Callers
decide on the content afterwards and read it again from the spool."""

import asyncio
import codecs
import hashlib
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import IO

from app.core.errors import AppError

MEMORY_BYTES = 1024 * 1024
HEAD_BYTES = 4096
CHUNK = 64 * 1024


class PayloadTooLarge(AppError):
    status_code = 413
    code = "request.too_large"


@dataclass
class Spooled:
    """The body: `size`, `sha256` (hex), its first bytes (`head`), whether it is all
    valid UTF-8 without NUL (`text`). Close it when done (`with`)."""

    file: IO[bytes]
    size: int = 0
    sha256: str = ""
    head: bytes = b""
    text: bool = True
    _hash: "hashlib._Hash" = field(default_factory=hashlib.sha256, repr=False)

    def __enter__(self) -> "Spooled":
        return self

    def __exit__(self, *exc: object) -> None:
        self.file.close()

    async def chunks(self) -> AsyncIterator[bytes]:
        """The body again, from the start."""
        await asyncio.to_thread(self.file.seek, 0)
        while chunk := await asyncio.to_thread(self.file.read, CHUNK):
            yield chunk


async def spool(stream: AsyncIterator[bytes], max_bytes: int, *, code: str) -> Spooled:
    """Read `stream` to the end; more than `max_bytes` is 413 with `code` (read no
    further than one chunk past the limit)."""
    spooled = Spooled(tempfile.SpooledTemporaryFile(max_size=MEMORY_BYTES))  # noqa: SIM115
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        async for chunk in stream:
            if not chunk:
                continue
            spooled.size += len(chunk)
            if spooled.size > max_bytes:
                raise PayloadTooLarge(code=code)
            if len(spooled.head) < HEAD_BYTES:
                spooled.head += chunk[: HEAD_BYTES - len(spooled.head)]
            spooled._hash.update(chunk)
            if spooled.text:
                spooled.text = _still_text(decoder, chunk)
            if spooled.size > MEMORY_BYTES:
                await asyncio.to_thread(spooled.file.write, chunk)
            else:
                spooled.file.write(chunk)
        if spooled.text:
            spooled.text = _still_text(decoder, b"", final=True)
    except BaseException:
        spooled.file.close()
        raise
    spooled.sha256 = spooled._hash.hexdigest()
    return spooled


def _still_text(decoder: codecs.IncrementalDecoder, chunk: bytes, *, final: bool = False) -> bool:
    if b"\x00" in chunk:
        return False
    try:
        decoder.decode(chunk, final=final)
    except UnicodeDecodeError:
        return False
    return True
