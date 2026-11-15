"""Facts about the current request that code deep inside it may need without every
signature passing them along: so far the client address (for the audit log).

Set by `RequestContextMiddleware` for the request's lifetime; outside a request (jobs,
bootstrap, tests calling services directly) the values are None. Nothing here is
logged.
"""

import asyncio
from contextvars import Context, ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

_client_ip: ContextVar[str | None] = ContextVar("herd_client_ip", default=None)


def client_ip() -> str | None:
    """The address the current request came from, as the server saw it."""
    return _client_ip.get()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        token = _client_ip.set(client[0] if client else None)
        try:
            await self.app(scope, receive, send)
        finally:
            _client_ip.reset(token)


class FreshContext:
    """Runs every request in an empty context (outermost, before tracing).

    A server task for the next request on a keep-alive connection copies the context
    of the connection's read callback, and that callback captures the context of
    whichever request last resumed reading (uvicorn's flow control on bodies over
    64 KiB). Without this, the next requests on the connection would continue the
    upload's trace (one trace id for many requests) and carry its log fields (review
    M2 R11)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        await asyncio.create_task(self._run(scope, receive, send), context=Context())

    async def _run(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
