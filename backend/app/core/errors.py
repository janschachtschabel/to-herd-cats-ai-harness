"""Application errors and their JSON shape: {"error": {"code", "message", "trace_id"}}."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


def new_trace_id() -> str:
    return uuid.uuid4().hex


def _trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", "") or new_trace_id())


def _body(request: Request, code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message, "trace_id": _trace_id(request)}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_body(request, exc.code, exc.message)
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors() if e.get("loc"))
        message = f"Invalid request: {fields}" if fields else "Invalid request"
        return JSONResponse(status_code=422, content=_body(request, "validation_failed", message))

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled exception", exc_info=exc, extra={"path": request.url.path})
        return JSONResponse(
            status_code=500, content=_body(request, "internal", "Internal server error")
        )
