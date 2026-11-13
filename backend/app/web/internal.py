"""The internal application (port HERD_INTERNAL_PORT): probes, metrics and the
internal collab API. In a process that runs the worker, `/ready` also needs the
worker's loop to be running and to reach the database.

Never reachable through the public port and not part of the public OpenAPI document.
`/internal/*` needs the header `X-Herd-Internal-Token` equal to HERD_INTERNAL_TOKEN
(compared in constant time); without a configured token it answers 503.
"""

import asyncio
import hmac
import logging
from typing import Protocol

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.body_limit import BodyLimitMiddleware
from app.core.config import get_settings
from app.core.db import get_database
from app.core.errors import AppError, Unauthorized, UnhandledErrorMiddleware, install_error_handlers
from app.core.metrics import render_metrics
from app.core.migrations import schema_is_compatible
from app.core.request_context import FreshContext
from app.modules.wiki.collab_router import router as collab_router

logger = logging.getLogger(__name__)

READY_TIMEOUT_SECONDS = 2.0
INTERNAL_TOKEN_HEADER = "x-herd-internal-token"  # noqa: S105 (a header name)
# A live save carries a Yjs state of up to 5 MB in base64 and up to 200,000 characters.
INTERNAL_MAX_BODY_BYTES = 9 * 1024 * 1024


class InternalDisabled(AppError):
    status_code = 503
    code = "internal.disabled"


async def internal_token_guard(request: Request) -> None:
    expected = get_settings().internal_token
    if expected is None:
        raise InternalDisabled()
    given = request.headers.get(INTERNAL_TOKEN_HEADER, "")
    if not hmac.compare_digest(given.encode("utf-8"), expected.get_secret_value().encode("utf-8")):
        raise Unauthorized(code="internal.unauthorized")


def internal_router() -> APIRouter:
    internal = APIRouter(prefix="/internal", dependencies=[Depends(internal_token_guard)])
    internal.include_router(collab_router)
    return internal


class Readiness(Protocol):
    """Something in the process whose state `/ready` reports too (the worker)."""

    @property
    def ready(self) -> bool: ...


def get_engine() -> AsyncEngine:
    return get_database().engine


def _not_ready(reason: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": reason})


def create_internal_app(*, worker: Readiness | None = None) -> FastAPI:
    """With `worker`, `/ready` also waits for the worker's loop (roles worker and all)."""
    app = FastAPI(title="to-herd-cats-ai internal", openapi_url=None, docs_url=None, redoc_url=None)
    app.add_middleware(BodyLimitMiddleware, max_bytes=INTERNAL_MAX_BODY_BYTES)
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(FreshContext)  # outermost: no context of an earlier request
    install_error_handlers(app)
    app.include_router(internal_router())

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: the process answers. No database, so a database outage restarts nothing."""
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    async def ready(engine: AsyncEngine = Depends(get_engine)) -> dict[str, str] | JSONResponse:
        try:
            async with asyncio.timeout(READY_TIMEOUT_SECONDS):
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                compatible = await schema_is_compatible(engine)
        except Exception as exc:  # any failure to reach the database means "not ready"
            logger.warning("readiness: database unreachable", extra={"error": type(exc).__name__})
            return _not_ready("database")
        if not compatible:
            return _not_ready("migrations")
        if worker is not None and not worker.ready:
            return _not_ready("worker")
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = render_metrics()
        return Response(content=body, media_type=content_type)

    return app
