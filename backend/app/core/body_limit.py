"""The request body limit (`HERD_MAX_BODY_BYTES`, default 1 MiB): 413 in the error shape.

It runs before anything reads the body (the NUL guard, routing, CSRF, authentication),
so an oversized body is never buffered: a declared `Content-Length` over the limit is
refused unread, and a body without one (chunked) is counted while it is read and cut
off at the first chunk over the limit. `limit_for` is where a route would get a limit
of its own; so far every request has the same.
"""

from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body

CODE = "request.too_large"
MESSAGE = "Request body too large"


class BodyTooLarge(HTTPException):
    """Raised from `receive`: a route that reads the body answers 413 through the
    error handlers; anything else that reads it is answered here."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail=MESSAGE)


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None  # malformed: the server refuses it; reading is still counted
    return None


async def refuse(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(status_code=413, content=error_body(CODE, MESSAGE))
    await response(scope, receive, send)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def limit_for(self, scope: Scope) -> int:
        return self.max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope)
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await refuse(scope, receive, send)
            return
        received = 0
        started = False

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLarge()
            return message

        async def watched(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted, watched)
        except BodyTooLarge:
            if started:  # too late for an answer; the server closes the connection
                return
            await refuse(scope, receive, send)
