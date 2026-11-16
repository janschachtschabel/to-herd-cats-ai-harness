"""The WebSocket relay `/collab/{page_id}?generation=N` on the public port (spec E13,
plan M2 task 9, plan M9 decision 16): browsers reach the collab process through the
API, which runs the same checks as the REST API before a single frame passes.

1. Origin: equal to HERD_PUBLIC_URL's origin, or without one, to the host the
   request came to; otherwise the handshake is refused (HTTP 403). This replaces the
   CSRF header, which a browser cannot add to a WebSocket handshake.
2. Session cookie (4401), the page visible (4404) and `page.edit` (4403), and the
   browser's document of the current generation (4409), through
   `CollabService.admit`, in a database session of its own that is committed and
   closed before relaying (a live connection holds no database connection). It
   issues a grant for this connection, page and generation (`collab_grants.py`).
3. Then the collab process is dialled at `<collab_url>/collab/<page_id>?generation=N`
   with only the grant (`Authorization: Bearer herd_cg_...`), the Origin and the
   original host (`X-Forwarded-Host`). The session cookie never leaves the API: a
   compromised collab process reaches only the pages open in it and no login session.
   The page comes from the path the check ran on, and the collab process binds the
   connection to it. Frames pass both ways unchanged; a close code (4409, 4403, ...)
   is passed on.

Without HERD_INTERNAL_TOKEN live editing is off (4503 `collab.disabled`), and so it is
in maintenance (4503 `maintenance.active`, plan M9 decision 9); a collab process that cannot
be reached is 4502. A refusal after the Origin check accepts the socket and closes it
at once with `4000 + HTTP status` and the error code as the reason, before a frame
passes: a browser cannot read the status of a refused handshake, but it can read a
close code (the same codes the collab process closes with). Nothing of the headers
or frames is logged.
"""

import asyncio
import logging
import uuid
from contextlib import suppress
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from app.core.config import Settings, get_settings
from app.core.db import get_database
from app.core.errors import AppError
from app.core.metrics import COLLAB_CONNECTIONS
from app.modules.auth.cookies import session_token
from app.modules.maintenance.cache import in_maintenance
from app.modules.wiki.collab_models import MAX_YDOC_BYTES
from app.modules.wiki.collab_service import CollabService

logger = logging.getLogger(__name__)

router = APIRouter()

# One limit with the collab process (review M2 U3; `collab/size.mjs`, checked by a
# test): it keeps a live state of up to MAX_YDOC_BYTES (the API's cap on a saved state)
# and sends a joining browser the whole state in one message, so a message may be that
# large plus its envelope (document name, message type, lengths). The relay passes
# what the collab process allows, both ways.
MESSAGE_ENVELOPE_BYTES = 64 * 1024
MAX_MESSAGE_BYTES = MAX_YDOC_BYTES + MESSAGE_ENVELOPE_BYTES
OPEN_TIMEOUT_SECONDS = 5.0
# Checking and dialling together; then the collab process gives the browser 10 s to
# join its document (4408), so no socket idles before it is live (review M2 R7).
HANDSHAKE_TIMEOUT_SECONDS = 10.0


def origin_allowed(origin: str | None, host: str | None, public_url: str | None) -> bool:
    """HERD_PUBLIC_URL's origin exactly; without one, the Origin's host must be the
    host the browser connected to."""
    if not origin:
        return False
    if public_url:
        url = urlsplit(public_url)
        return origin == f"{url.scheme}://{url.netloc}"
    return bool(host) and urlsplit(origin).netloc.lower() == (host or "").lower()


async def _refuse_origin(websocket: WebSocket) -> None:
    """Closed before the handshake completes: the server answers HTTP 403."""
    await websocket.close(code=1008)


async def _deny(websocket: WebSocket, status: int, code: str) -> None:
    """Accepted and closed at once with `4000 + status`; no frame passes."""
    await websocket.accept()
    await websocket.close(code=4000 + status, reason=code)


async def _authorize(token: str, page_id: uuid.UUID, generation: int) -> str | AppError:
    """A grant for this connection, or why there is none."""
    async with get_database().session_factory() as session:
        try:
            grant = await CollabService(session).admit(token, page_id, generation)
        except AppError as error:
            await session.rollback()
            return error
        await session.commit()
    return grant


@router.websocket("/collab/{page_id}")
async def collab_relay(websocket: WebSocket, page_id: uuid.UUID) -> None:
    settings = get_settings()
    host = websocket.headers.get("host")
    if not origin_allowed(websocket.headers.get("origin"), host, settings.public_url):
        return await _refuse_origin(websocket)
    if settings.internal_token is None:
        return await _deny(websocket, 503, "collab.disabled")
    if in_maintenance():
        return await _deny(websocket, 503, "maintenance.active")
    raw_generation = websocket.query_params.get("generation", "")
    if not raw_generation.isdigit() or len(raw_generation) > 9:
        return await _deny(websocket, 400, "collab.generation_invalid")
    token = session_token(websocket, settings)
    if not token:
        return await _deny(websocket, 401, "auth.required")
    generation = int(raw_generation)
    try:
        async with asyncio.timeout(HANDSHAKE_TIMEOUT_SECONDS):
            grant = await _authorize(token, page_id, generation)
            if isinstance(grant, AppError):
                return await _deny(websocket, grant.status_code, grant.code)
            upstream = await _dial(websocket, settings, grant, host, page_id, generation)
    except TimeoutError:
        logger.warning("collab handshake timed out")
        return await _deny(websocket, 504, "collab.timeout")
    if upstream is None:
        return await _deny(websocket, 502, "collab.unavailable")
    # Whatever happens from here on (the browser may be gone already), the upstream
    # connection ends with it: left open, it held one of the login session's slots in
    # the collab process until its handshake timeout (review M2 U11).
    try:
        await websocket.accept()
        COLLAB_CONNECTIONS.inc()
        try:
            await _relay(websocket, upstream)
        finally:
            COLLAB_CONNECTIONS.dec()
    finally:
        await upstream.close()


async def _dial(
    websocket: WebSocket,
    settings: Settings,
    grant: str,
    host: str | None,
    page_id: uuid.UUID,
    generation: int,
) -> ClientConnection | None:
    """The collab process for this page; None when it cannot be reached."""
    try:
        return await connect(
            f"{settings.collab_url}/collab/{page_id}?generation={generation}",
            additional_headers=_upstream_headers(websocket, grant, host),
            max_size=MAX_MESSAGE_BYTES,
            open_timeout=OPEN_TIMEOUT_SECONDS,
            compression=None,
        )
    except (OSError, InvalidHandshake, TimeoutError) as exc:
        logger.warning("collab unreachable", extra={"error": type(exc).__name__})
        return None


def _upstream_headers(websocket: WebSocket, grant: str, host: str | None) -> dict[str, str]:
    """The grant, the Origin and the host only: no cookie, nothing else of the browser's."""
    headers = {"Authorization": f"Bearer {grant}", "Origin": websocket.headers["origin"]}
    if host:
        headers["X-Forwarded-Host"] = host
    return headers


async def _relay(websocket: WebSocket, upstream: ClientConnection) -> None:
    """Both directions until one side closes; its close code goes to the other."""

    async def downstream_to_upstream() -> None:
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    await upstream.close(_client_code(message.get("code", 1000)))
                    return
                data = message.get("bytes")
                await upstream.send(data if data is not None else message.get("text", ""))
        except (WebSocketDisconnect, ConnectionClosed):
            await upstream.close()

    async def upstream_to_downstream() -> None:
        try:
            async for data in upstream:
                if isinstance(data, bytes):
                    await websocket.send_bytes(data)
                else:
                    await websocket.send_text(data)
        except ConnectionClosed:
            pass
        code = upstream.close_code if upstream.close_code is not None else 1011
        reason = upstream.close_reason or ""
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close(code=_client_code(code), reason=reason)

    tasks = [
        asyncio.create_task(downstream_to_upstream()),
        asyncio.create_task(upstream_to_downstream()),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await upstream.close()


def _client_code(code: int) -> int:
    """Codes that may be sent in a close frame (1005/1006/1015 may not)."""
    return code if code in (1000, 1001, 1008, 1011, 1012, 1013) or 3000 <= code < 5000 else 1011
