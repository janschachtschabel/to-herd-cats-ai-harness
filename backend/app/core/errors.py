"""Application errors and their JSON shape: {"error": {"code", "message", "trace_id"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.telemetry import current_trace_ids

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        # The specific code first: a message-less error should say its specific code.
        if code:
            self.code = code
        self.message = message or self.code
        super().__init__(self.message)


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def _body(code: str, message: str) -> dict[str, dict[str, str]]:
    # The active span's trace id: the same one the log lines of this request carry.
    return {"error": {"code": code, "message": message, "trace_id": current_trace_ids()[0]}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Raised by routing itself: no route (404), wrong method (405, with `Allow`).
        code = _HTTP_CODES.get(exc.status_code, f"http.{exc.status_code}")
        return JSONResponse(
            status_code=exc.status_code, content=_body(code, code), headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors() if e.get("loc"))
        message = f"Invalid request: {fields}" if fields else "Invalid request"
        return JSONResponse(status_code=422, content=_body("validation_failed", message))


class UnhandledErrorMiddleware:
    """Any other exception: logged once, answered with a 500 in the error shape.

    It is not re-raised (Starlette's own handler would, and the server would log it a
    second time, outside our formatting), and it is answered inside the middleware
    stack, so the security headers and the request line see the 500. exc_info only:
    no body, no headers; database errors are logged without their data (logging)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            logger.error("unhandled exception", exc_info=exc)
            if started:  # too late for an answer; the server closes the connection
                return
            response = JSONResponse(
                status_code=500, content=_body("internal", "Internal server error")
            )
            await response(scope, receive, send)
