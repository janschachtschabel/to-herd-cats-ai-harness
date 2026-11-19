"""An optional virus scan of uploads (ASVS 5.0 V5.4.3, plan M9 task 18, J11): clamd,
run by the operator as a service of its own and reached over TCP with its `zINSTREAM`
command (our own client, no library and nothing linked). Off unless
HERD_CLAMAV_ADDRESS (`host:port`) is set; then attachments, wiki imports and skill
imports are scanned before they are stored, while the request holds no transaction (so
no pooled connection waits for clamd), and the scan fails closed:

- a find: 422 `attachment.rejected_by_scan`;
- a scanner that cannot be reached, answers with an error (clamd's StreamMaxLength
  below the upload limits, for one) or takes longer than `SCAN_SECONDS`: 503
  `attachment.scan_unavailable`; nothing is stored.

Neither the file's name nor its content goes into a log line or a metric: the outcome
alone (`herd_virus_scans_total{outcome}`, `clean`, `found`, `failed`). Uploaded backup
archives are not scanned: owner-only, a database dump, never served to others."""

import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.core.errors import AppError, ValidationFailed
from app.core.metrics import VIRUS_SCANS

logger = logging.getLogger(__name__)

SCAN_SECONDS = 120.0  # the whole scan, sending included (an import may be 100 MiB)
CHUNK = 64 * 1024  # clamd takes chunks up to its StreamMaxLength; small ones are safe
REPLY_MAX = 4096


class ScanUnavailable(AppError):
    status_code = 503
    code = "attachment.scan_unavailable"


def _found() -> ValidationFailed:
    return ValidationFailed("rejected by the virus scan", code="attachment.rejected_by_scan")


async def scan(settings: Settings, chunks: AsyncIterator[bytes]) -> None:
    """Scan the stream with clamd, if one is configured; raises on a find or failure."""
    address = settings.clamav_address
    if not address:
        return
    host, _, port = address.rpartition(":")
    host = host.removeprefix("[").removesuffix("]")  # an IPv6 address in brackets
    try:
        async with asyncio.timeout(SCAN_SECONDS):
            reply = await _instream(host, int(port), chunks)
    except (OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        VIRUS_SCANS.labels(outcome="failed").inc()
        logger.warning("virus_scan.unavailable", extra={"error": type(exc).__name__})
        raise ScanUnavailable() from None
    if reply.endswith(b" OK"):
        VIRUS_SCANS.labels(outcome="clean").inc()
        return
    if reply.endswith(b" FOUND"):
        VIRUS_SCANS.labels(outcome="found").inc()
        logger.warning("virus_scan.found")
        raise _found()
    VIRUS_SCANS.labels(outcome="failed").inc()
    logger.warning("virus_scan.error")  # clamd's ERROR line names no content
    raise ScanUnavailable()


async def _instream(host: str, port: int, chunks: AsyncIterator[bytes]) -> bytes:
    reader, writer = await asyncio.open_connection(host, port, limit=REPLY_MAX)
    try:
        writer.write(b"zINSTREAM\0")
        async for chunk in chunks:
            for start in range(0, len(chunk), CHUNK):
                part = chunk[start : start + CHUNK]
                writer.write(len(part).to_bytes(4, "big") + part)
                await writer.drain()
        writer.write(b"\0\0\0\0")
        await writer.drain()
        return (await reader.readuntil(b"\0")).rstrip(b"\0")
    finally:
        writer.close()
