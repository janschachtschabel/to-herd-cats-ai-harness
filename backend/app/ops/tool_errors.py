"""Why a PostgreSQL tool failed, fit for a log line (R18-2).

A tool's stderr is read (its first `LIMIT` bytes) and, on failure, one line of it goes
into the log: the tool's own connection-level error (`pg_dump: error: connection to
server … failed: root certificate file … does not exist`), which names hosts, ports and
files, never data. An error the server raised while running SQL (`… ERROR: …`, `DETAIL:`)
may quote values from the dump, so it is logged only as `query failed`. Anything that
looks like a password or a URL's user information is masked as well, although libpq
does not print either.
"""

import asyncio
import logging
import re

logger = logging.getLogger(__name__)

LIMIT = 8192
MAX_REASON = 300
QUERY_FAILED = "query failed"
_TOOL_ERROR = re.compile(r"^(?:pg_dump|pg_restore|psql): error: (.+)$")
_SERVER_TEXT = re.compile(r"\b(?:ERROR|FATAL|DETAIL|HINT|LINE \d+):")
_PASSWORD = re.compile(r"(password\s*=\s*)\S+", re.IGNORECASE)
_USERINFO = re.compile(r"(://)[^/@\s]*@")


def collect(stream: asyncio.StreamReader | None) -> "asyncio.Task[bytes]":
    """Read `stream` to its end in the background, keeping its first `LIMIT` bytes (so
    a chatty tool never blocks on a full pipe)."""

    async def read() -> bytes:
        if stream is None:
            return b""
        kept = bytearray()
        while chunk := await stream.read(65536):
            if len(kept) < LIMIT:
                kept.extend(chunk[: LIMIT - len(kept)])
        return bytes(kept)

    return asyncio.create_task(read())


def reason(stderr: bytes) -> str | None:
    """The tool's first error line, masked and cut; `QUERY_FAILED` for an error the
    server raised running SQL; None when the tool said nothing that explains it."""
    for raw in stderr.decode("utf-8", "replace").splitlines():
        match = _TOOL_ERROR.match(raw.strip())
        if match is None:
            continue
        line = match.group(1)
        if _SERVER_TEXT.search(line):
            return QUERY_FAILED
        line = _USERINFO.sub(r"\1***@", _PASSWORD.sub(r"\1***", line))
        return line[:MAX_REASON]
    return None


async def log_failure(
    tool: str, code: str, status: int | None, stderr: "asyncio.Task[bytes]"
) -> None:
    """One warning naming the tool, the code, the exit status and the reason."""
    try:
        said = await asyncio.wait_for(stderr, timeout=5)
    except (TimeoutError, OSError):
        said = b""
    logger.warning(
        "backup.tool_failed",
        extra={"tool": tool, "code": code, "status": status, "reason": reason(said)},
    )
