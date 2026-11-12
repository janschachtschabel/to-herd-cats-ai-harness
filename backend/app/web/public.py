"""The public application (port HERD_PUBLIC_PORT)."""

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.request_log import RequestLogMiddleware
from app.core.telemetry import configure_tracing


def create_public_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="to-herd-cats-ai",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(RequestLogMiddleware)
    install_error_handlers(app)
    configure_tracing(app, settings)

    if settings.environment == "test":
        from app.web.test_routes import router as test_router

        app.include_router(test_router, prefix="/api")
    return app
