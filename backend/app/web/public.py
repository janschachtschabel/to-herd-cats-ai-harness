"""The public application (port HERD_PUBLIC_PORT)."""

import re

from fastapi import APIRouter, Depends, FastAPI

from app.core.body_limit import BodyLimitMiddleware, RouteLimit
from app.core.config import Settings, get_settings
from app.core.errors import UnhandledErrorMiddleware, install_error_handlers
from app.core.nul_guard import NulGuardMiddleware
from app.core.request_context import RequestContextMiddleware
from app.core.request_log import RequestLogMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.telemetry import configure_tracing
from app.modules.audit.router import router as audit_router
from app.modules.auth.deps import csrf_guard
from app.modules.auth.router import router as auth_router
from app.modules.directory.router import router as directory_router
from app.modules.groups.router import router as groups_router
from app.modules.messaging import router as messaging
from app.modules.search.router import router as search_router
from app.modules.spaces.router import router as spaces_router
from app.modules.tags.router import router as tags_router
from app.modules.users.router import router as users_router
from app.modules.wiki import router as wiki
from app.modules.wiki.attachments_router import attachments, page_attachments
from app.modules.wiki.transfer_router import page_export, space_transfer
from app.modules.wiki.versions_router import page_versions
from app.web.collab_proxy import router as collab_relay
from app.web.spa import mount_spa


def api_router() -> APIRouter:
    """Everything under /api; unsafe methods need the CSRF header."""
    api = APIRouter(prefix="/api", dependencies=[Depends(csrf_guard)])
    api.include_router(auth_router)
    api.include_router(users_router)
    api.include_router(groups_router)
    api.include_router(spaces_router)
    api.include_router(wiki.space_pages)
    api.include_router(wiki.pages)
    api.include_router(wiki.space_trash)
    api.include_router(page_versions)
    api.include_router(page_attachments)
    api.include_router(attachments)
    api.include_router(space_transfer)
    api.include_router(page_export)
    api.include_router(tags_router)
    api.include_router(messaging.space_channels)
    api.include_router(messaging.channels)
    api.include_router(messaging.conversations)
    api.include_router(messaging.messages)
    api.include_router(search_router)
    api.include_router(directory_router)
    api.include_router(audit_router)
    return api


def body_limits(settings: Settings) -> list[RouteLimit]:
    """The routes that take files, with their own request body limit."""
    return [
        RouteLimit(
            "POST", re.compile(r"/api/pages/[^/]+/attachments"), settings.attachment_max_bytes
        ),
        RouteLimit("POST", re.compile(r"/api/spaces/[^/]+/import"), settings.import_max_bytes),
    ]


def create_public_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="to-herd-cats-ai",
        openapi_url="/api/openapi.json",
        # Swagger UI loads its scripts from a CDN: never in production, where the
        # browser makes no third-party requests. /api/openapi.json stays.
        docs_url=None if settings.environment == "production" else "/api/docs",
        redoc_url=None,
    )
    # Added first is innermost: errors are answered before the request line is written.
    app.add_middleware(NulGuardMiddleware)
    app.add_middleware(
        BodyLimitMiddleware, max_bytes=settings.max_body_bytes, routes=body_limits(settings)
    )
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestLogMiddleware)
    install_error_handlers(app)
    configure_tracing(app, settings)
    app.include_router(api_router())
    app.include_router(collab_relay)  # WebSocket /collab/{page_id}

    if settings.environment == "test":
        from app.web.test_routes import router as test_router

        app.include_router(test_router, prefix="/api")
    if settings.static_dir is not None:
        mount_spa(app, settings.static_dir)  # last: it answers every other path
    return app
