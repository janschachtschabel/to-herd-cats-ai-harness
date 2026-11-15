"""Text containing a NUL character is refused with 422 before any route sees it.

PostgreSQL cannot store 0x00 in text, so such input would otherwise fail deep down as a
500. One check at the edge covers every field: the path, the query string (raw or
%00) and JSON bodies (the escape `\\u0000`; an escaped backslash before `u0000` is
text, not a NUL). Cursors carry text inside base64 and are checked where they are
decoded (`core.pagination`).
"""

import asyncio
import re

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body

MESSAGE = "Text must not contain NUL characters"
# An odd number of backslashes, then u0000: a JSON escape of NUL.
_JSON_NUL = re.compile(rb"(?<!\\)(?:\\\\)*\\u0000")
# Bodies larger than this are scanned in a worker thread, not in the event loop.
OFF_LOOP_BYTES = 256 * 1024


def contains_nul(body: bytes) -> bool:
    """Linear: two substring searches; the regex runs only if the escape occurs."""
    return b"\x00" in body or (b"\\u0000" in body and _JSON_NUL.search(body) is not None)


def _has_nul_in_url(scope: Scope) -> bool:
    query: bytes = scope.get("query_string", b"")
    return "\x00" in scope["path"] or b"\x00" in query or b"%00" in query


def _is_json(scope: Scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"content-type":
            return b"json" in value.lower()
    return False


class NulGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if _has_nul_in_url(scope):
            await self._refuse(scope, receive, send)
            return
        if not _is_json(scope):
            await self.app(scope, receive, send)
            return
        # Read the body once (the body limit, outside, bounds it), check it, then hand
        # the same messages to the app. Chunks are joined once: linear in the size.
        messages: list[Message] = []
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request" or not message.get("more_body", False):
                break
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.request")
        if len(body) > OFF_LOOP_BYTES:
            found = await asyncio.to_thread(contains_nul, body)
        else:
            found = contains_nul(body)
        del body  # the messages keep the chunks; no second copy while the app runs
        if found:
            await self._refuse(scope, receive, send)
            return

        async def replay() -> Message:
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(status_code=422, content=error_body("validation_failed", MESSAGE))
        await response(scope, receive, send)
