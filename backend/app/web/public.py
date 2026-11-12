"""The public application (port HERD_PUBLIC_PORT)."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.core.config import get_settings
from app.core.errors import install_error_handlers, new_trace_id


def create_public_app() -> FastAPI:
    app = FastAPI(
        title="to-herd-cats-ai",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def trace_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Replaced by the OpenTelemetry trace id in the observability task.
        request.state.trace_id = new_trace_id()
        return await call_next(request)

    install_error_handlers(app)

    if get_settings().environment == "test":
        from app.web.test_routes import router as test_router

        app.include_router(test_router, prefix="/api")
    return app
