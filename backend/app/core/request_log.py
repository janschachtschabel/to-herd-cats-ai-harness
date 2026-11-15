"""One `http.request` line per request (method, route template, status, duration), and
the matching HTTP metrics.

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

from app.core.logging import log_context, request_fields
from app.core.metrics import record_http_request

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

    FastAPI leaves an API route in `scope["route"]`, but its `path` lacks the prefix of
    the router it was included with; plain routes (OpenAPI, docs) leave only their
    endpoint. `iter_route_contexts` knows every route's full path.
    """
    route, endpoint = scope.get("route"), scope.get("endpoint")
    if route is None and endpoint is None:
        return None
    for context in iter_route_contexts(getattr(scope.get("app"), "routes", [])):
        original = context.original_route
        if original is route or (route is None and getattr(original, "endpoint", None) is endpoint):
            return context.path
    return None


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
        with log_context(**fields), request_fields() as bound:
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                seconds = time.perf_counter() - start
                route = route_template(scope)
                record_http_request(scope["method"], route, status, seconds)
                logger.info(
                    "http.request",
                    extra={
                        **bound,
                        "method": scope["method"],
                        "path": route or scope["path"],
                        "status": status,
                        "duration_ms": round(seconds * 1000, 2),
                    },
                )
