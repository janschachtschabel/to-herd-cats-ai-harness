"""Text containing a NUL character is refused with 422 before any route sees it.

PostgreSQL cannot store 0x00 in text, so such input would otherwise fail deep down as a
500. One check at the edge covers every field: the path, the query string (raw or
%00) and JSON bodies (the escape `\\u0000`; an escaped backslash before `u0000` is
text, not a NUL). Cursors carry text inside base64 and are checked where they are
decoded (`core.pagination`).
"""

import re

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body

MESSAGE = "Text must not contain NUL characters"
# An odd number of backslashes, then u0000: a JSON escape of NUL.
_JSON_NUL = re.compile(rb"(?<!\\)(?:\\\\)*\\u0000")


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
        # Read the body once, check it, then hand the same messages to the app.
        messages: list[Message] = []
        body = b""
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        if b"\x00" in body or _JSON_NUL.search(body):
            await self._refuse(scope, receive, send)
            return

        async def replay() -> Message:
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(status_code=422, content=error_body("validation_failed", MESSAGE))
        await response(scope, receive, send)
