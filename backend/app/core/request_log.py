"""One `http.request` line per request: method, route template, status, duration.

Header values, cookies and bodies are never logged. The one header that is read,
`x-client-trace-id`, is a correlation id the client chose; it is logged only when it
looks like one (short, no whitespace or control characters).
"""

import logging
import re
import time
from typing import Any

from fastapi.routing import iter_route_contexts
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import log_context

logger = logging.getLogger("app.request")

CLIENT_TRACE_HEADER = b"x-client-trace-id"
_CLIENT_TRACE_ID = re.compile(r"[A-Za-z0-9._:-]{1,64}")


def _client_trace_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == CLIENT_TRACE_HEADER:
            text = value.decode("latin-1")
            return text if _CLIENT_TRACE_ID.fullmatch(text) else None
    return None


def route_template(scope: Scope) -> str | None:
    """The matched route's full path template (`/api/items/{id}`), None if nothing matched.

    FastAPI leaves the matched route in `scope["route"]`, but for routes from an included
    router its `path` lacks the include prefix; `iter_route_contexts` knows the full one.
    """
    route, app = scope.get("route"), scope.get("app")
    if route is None:
        return None
    for context in iter_route_contexts(getattr(app, "routes", [])):
        if context.original_route is route and context.path:
            return context.path
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else None


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status = 500  # an exception that escapes the app is answered with 500 further out
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        client_trace_id = _client_trace_id(scope)
        fields: dict[str, Any] = {"client_trace_id": client_trace_id} if client_trace_id else {}
        with log_context(**fields):
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                logger.info(
                    "http.request",
                    extra={
                        "method": scope["method"],
                        "path": route_template(scope) or scope["path"],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    },
                )
