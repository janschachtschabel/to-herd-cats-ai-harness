"""Reading an uploaded body once, with a size limit: kept in memory up to 1 MiB, in a
temporary file under HERD_DATA_DIR/tmp beyond (`core/spool.py`), hashed (SHA-256) and
checked for UTF-8 on the way. Callers decide on the content afterwards and read it again
from the spool."""

import asyncio
import codecs
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import IO

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.spool import spooled_file

MEMORY_BYTES = 1024 * 1024
HEAD_BYTES = 4096
CHUNK = 64 * 1024


class PayloadTooLarge(AppError):
    status_code = 413
    code = "request.too_large"


class BodyReadTimeout(AppError):
    """No part of the body arrived for `HERD_BODY_READ_TIMEOUT_SECONDS`, or the whole
    body took longer than `HERD_BODY_TOTAL_TIMEOUT_SECONDS`."""

    status_code = 408
    code = "request.timeout"


async def arriving(
    stream: AsyncIterator[bytes], seconds: float, total: float
) -> AsyncIterator[bytes]:
    """`stream`, refused with 408 when the next part takes longer than `seconds` or the
    whole stream longer than `total` (review M2 S11)."""
    parts = aiter(stream)
    deadline = asyncio.get_running_loop().time() + total
    while True:
        try:
            async with asyncio.timeout_at(
                min(deadline, asyncio.get_running_loop().time() + seconds)
            ):
                chunk = await anext(parts)
        except StopAsyncIteration:
            return
        except TimeoutError:
            raise BodyReadTimeout() from None
        yield chunk


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
    further than one chunk past the limit), a body that stops arriving 408. Callers
    hold no database connection meanwhile (they end their transaction first)."""
    spooled = Spooled(spooled_file(MEMORY_BYTES))
    decoder = codecs.getincrementaldecoder("utf-8")()
    settings = get_settings()
    try:
        parts = arriving(
            stream, settings.body_read_timeout_seconds, settings.body_total_timeout_seconds
        )
        async for chunk in parts:
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
