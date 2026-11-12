"""The internal application (port HERD_INTERNAL_PORT): probes and metrics.

Never reachable through the public port and not part of the public OpenAPI document.
"""

import asyncio
import logging

from fastapi import Depends, FastAPI, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import get_database
from app.core.metrics import render_metrics
from app.core.migrations import schema_is_compatible

logger = logging.getLogger(__name__)

READY_TIMEOUT_SECONDS = 2.0


def get_engine() -> AsyncEngine:
    return get_database().engine


def _not_ready(reason: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": reason})


def create_internal_app() -> FastAPI:
    app = FastAPI(title="to-herd-cats-ai internal", openapi_url=None, docs_url=None, redoc_url=None)

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
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = render_metrics()
        return Response(content=body, media_type=content_type)

    return app
