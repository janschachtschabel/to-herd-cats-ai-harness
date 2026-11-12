"""Application errors and their JSON shape: {"error": {"code", "message", "trace_id"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


def _body(code: str, message: str) -> dict[str, dict[str, str]]:
    # The active span's trace id: the same one the log lines of this request carry.
    return {"error": {"code": code, "message": message, "trace_id": current_trace_ids()[0]}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors() if e.get("loc"))
        message = f"Invalid request: {fields}" if fields else "Invalid request"
        return JSONResponse(status_code=422, content=_body("validation_failed", message))

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        # exc_info only: no body, no headers. The request line carries method and route.
        logger.error("unhandled exception", exc_info=exc)
        return JSONResponse(status_code=500, content=_body("internal", "Internal server error"))
