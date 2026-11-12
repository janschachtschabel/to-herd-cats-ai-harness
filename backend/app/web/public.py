"""The public application (port HERD_PUBLIC_PORT)."""

from fastapi import APIRouter, Depends, FastAPI

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.request_context import RequestContextMiddleware
from app.core.request_log import RequestLogMiddleware
from app.core.telemetry import configure_tracing
from app.modules.audit.router import router as audit_router
from app.modules.auth.deps import csrf_guard
from app.modules.auth.router import router as auth_router
from app.modules.groups.router import router as groups_router
from app.modules.spaces.router import router as spaces_router
from app.modules.users.router import router as users_router


def api_router() -> APIRouter:
    """Everything under /api; unsafe methods need the CSRF header."""
    api = APIRouter(prefix="/api", dependencies=[Depends(csrf_guard)])
    api.include_router(auth_router)
    api.include_router(users_router)
    api.include_router(groups_router)
    api.include_router(spaces_router)
    api.include_router(audit_router)
    return api


def create_public_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="to-herd-cats-ai",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestLogMiddleware)
    install_error_handlers(app)
    configure_tracing(app, settings)
    app.include_router(api_router())

    if settings.environment == "test":
        from app.web.test_routes import router as test_router

        app.include_router(test_router, prefix="/api")
    return app
