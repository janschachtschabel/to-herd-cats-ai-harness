"""Headers and bodies of file downloads."""

import asyncio
import re
from collections.abc import AsyncIterator
from typing import IO
from urllib.parse import quote

CHUNK = 64 * 1024
_UNSAFE_IN_QUOTES = re.compile(r"[^A-Za-z0-9 ._()-]")


def content_disposition(kind: str, filename: str) -> str:
    """RFC 6266/5987: an ASCII fallback without quotes, backslashes or control
    characters, and the exact name percent-encoded as UTF-8."""
    fallback = _UNSAFE_IN_QUOTES.sub("_", filename)
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


async def file_chunks(file: IO[bytes]) -> AsyncIterator[bytes]:
    """`file` from the start, in chunks; closed at the end (or when the client leaves)."""
    try:
        await asyncio.to_thread(file.seek, 0)
        while chunk := await asyncio.to_thread(file.read, CHUNK):
            yield chunk
    finally:
        file.close()
