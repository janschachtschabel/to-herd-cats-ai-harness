"""The public application (port HERD_PUBLIC_PORT)."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app.core.body_limit import BodyLimitMiddleware, RouteLimit
from app.core.config import Settings, get_settings
from app.core.db import get_database
from app.core.errors import UnhandledErrorMiddleware, install_error_handlers
from app.core.nul_guard import NulGuardMiddleware
from app.core.request_context import RequestContextMiddleware
from app.core.request_log import RequestLogMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.telemetry import configure_tracing
from app.mcp.endpoint import router as mcp_endpoint
from app.modules.agents import fresh_start_router, run_router
from app.modules.agents import router as agents_router
from app.modules.agents import spaces_router as agent_spaces
from app.modules.agents.approvals import router as approvals_router
from app.modules.ai import assignment_router as ai_assignments
from app.modules.ai import budget_router as ai_budgets
from app.modules.ai import router as ai
from app.modules.ai import usage_router as ai_usage
from app.modules.audit.router import router as audit_router
from app.modules.auth.deps import csrf_guard
from app.modules.auth.router import router as auth_router
from app.modules.auth.sessions_router import router as own_sessions_router
from app.modules.automations import router as automations_router
from app.modules.backups.replacing import replace_runner
from app.modules.backups.router import router as backups_router
from app.modules.connectors import router as connectors
from app.modules.directory.router import router as directory_router
from app.modules.groups.router import router as groups_router
from app.modules.maintenance.cache import maintenance_cache
from app.modules.maintenance.middleware import MaintenanceMiddleware
from app.modules.maintenance.router import router as maintenance_router
from app.modules.mcp_catalog import router as mcp_catalog
from app.modules.mcp_servers import router as mcp_servers
from app.modules.messaging import router as messaging
from app.modules.messaging import router_activity as messaging_activity
from app.modules.messaging import router_dms as messaging_dms
from app.modules.messaging import router_live as messaging_live
from app.modules.messaging import router_social as messaging_social
from app.modules.messaging.live import LiveHub
from app.modules.oauth import router as oauth
from app.modules.oidc import admin_router as oidc_admin
from app.modules.oidc.router import router as oidc_router
from app.modules.proposals import router as proposals
from app.modules.search.router import router as search_router
from app.modules.skills import assignment_router as skill_assignments
from app.modules.skills import proposal_router as skill_proposals
from app.modules.skills import router as skills
from app.modules.skills import transfer_router as skill_transfer
from app.modules.skills.transfer import MAX_IMPORT_BYTES as SKILL_IMPORT_MAX_BYTES
from app.modules.spaces.router import router as spaces_router
from app.modules.tags.router import router as tags_router
from app.modules.tickets import link_router as ticket_links
from app.modules.tickets import my_board_router as my_board
from app.modules.tickets import router as tickets
from app.modules.tickets import sprint_router as ticket_sprints
from app.modules.tickets import status_router as ticket_statuses
from app.modules.tickets import view_router as ticket_views
from app.modules.tokens import router as tokens_router
from app.modules.totp.router import router as totp_router
from app.modules.users.router import router as users_router
from app.modules.wiki import router as wiki
from app.modules.wiki.attachments_router import attachments, page_attachments
from app.modules.wiki.transfer_router import page_export, space_transfer
from app.modules.wiki.versions_router import page_versions
from app.version import app_version
from app.web.collab_proxy import router as collab_relay
from app.web.spa import mount_spa
from app.web.write_limits import COUNTED


def api_router() -> APIRouter:
    """Everything under /api; unsafe methods need the CSRF header. Writes to content
    count towards the person's write limit (`COUNTED`, `write_limits.py`)."""
    api = APIRouter(prefix="/api", dependencies=[Depends(csrf_guard)])
    api.include_router(maintenance_router)
    api.include_router(auth_router)
    api.include_router(own_sessions_router)
    api.include_router(totp_router)
    api.include_router(oidc_router)
    api.include_router(oidc_admin.providers)
    api.include_router(users_router)
    api.include_router(oidc_admin.user_identities)
    api.include_router(groups_router)
    api.include_router(spaces_router)
    api.include_router(wiki.space_pages, dependencies=COUNTED)
    api.include_router(wiki.pages, dependencies=COUNTED)
    api.include_router(wiki.space_trash, dependencies=COUNTED)
    api.include_router(page_versions, dependencies=COUNTED)
    api.include_router(proposals.space_proposals, dependencies=COUNTED)
    api.include_router(proposals.proposals, dependencies=COUNTED)
    api.include_router(page_attachments, dependencies=COUNTED)
    api.include_router(attachments, dependencies=COUNTED)
    api.include_router(space_transfer, dependencies=COUNTED)
    api.include_router(page_export)
    api.include_router(tags_router, dependencies=COUNTED)
    api.include_router(messaging.space_channels, dependencies=COUNTED)
    api.include_router(messaging.channels, dependencies=COUNTED)
    api.include_router(messaging_social.unread)  # before /conversations/{conversation_id}
    api.include_router(messaging.conversations, dependencies=COUNTED)
    api.include_router(messaging.messages, dependencies=COUNTED)
    api.include_router(messaging.page_threads, dependencies=COUNTED)
    api.include_router(tickets.ticket_threads, dependencies=COUNTED)
    api.include_router(messaging_social.reads)
    api.include_router(messaging_social.reactions, dependencies=COUNTED)
    api.include_router(messaging_activity.activity)
    api.include_router(messaging_dms.dms, dependencies=COUNTED)
    api.include_router(messaging_dms.dm_inspect)
    api.include_router(messaging_live.live)
    api.include_router(tickets.space_tickets, dependencies=COUNTED)
    api.include_router(ticket_views.ticket_counts)  # before /tickets/{number}
    api.include_router(my_board.my_board)  # before /tickets/{number}
    api.include_router(my_board.ticket_moves, dependencies=COUNTED)
    api.include_router(ticket_views.space_views)
    api.include_router(tickets.tickets, dependencies=COUNTED)
    api.include_router(ticket_links.ticket_pages, dependencies=COUNTED)
    api.include_router(ticket_links.page_tickets, dependencies=COUNTED)
    api.include_router(ticket_statuses.space_statuses)
    api.include_router(ticket_statuses.statuses)
    api.include_router(ticket_sprints.space_sprints, dependencies=COUNTED)
    api.include_router(ticket_sprints.sprints, dependencies=COUNTED)
    api.include_router(search_router)
    api.include_router(directory_router)
    api.include_router(audit_router)
    api.include_router(ai.connections)
    api.include_router(connectors.shared)
    api.include_router(connectors.personal)
    api.include_router(mcp_servers.servers)
    api.include_router(mcp_servers.personal)
    api.include_router(mcp_catalog.router)
    api.include_router(oauth.clients)
    api.include_router(oauth.callback)
    api.include_router(ai_assignments.assignments)
    api.include_router(ai_usage.usage)
    api.include_router(ai_budgets.budgets)
    api.include_router(tokens_router.mcp_admin)
    api.include_router(tokens_router.tokens)
    api.include_router(tokens_router.agent_tokens)
    api.include_router(agents_router.agents)
    api.include_router(run_router.agent_runs)
    api.include_router(run_router.runs)
    api.include_router(fresh_start_router.fresh_start)
    api.include_router(agent_spaces.agent_spaces)
    api.include_router(approvals_router.approvals)
    api.include_router(approvals_router.questions)
    api.include_router(automations_router.automations)
    api.include_router(automations_router.agent_automations)
    api.include_router(automations_router.space_automations)
    api.include_router(
        skill_transfer.skill_transfer, dependencies=COUNTED
    )  # before /skills/{skill_id}
    api.include_router(skills.skills)
    api.include_router(skill_assignments.agent_skills)
    api.include_router(skill_proposals.skill_proposals)
    api.include_router(backups_router)
    return api


def body_limits(settings: Settings) -> list[RouteLimit]:
    """The routes that take files, with their own request body limit."""
    return [
        RouteLimit(
            "POST", re.compile(r"/api/pages/[^/]+/attachments"), settings.attachment_max_bytes
        ),
        RouteLimit("POST", re.compile(r"/api/spaces/[^/]+/import"), settings.import_max_bytes),
        RouteLimit("POST", re.compile(r"/api/skills/import"), SKILL_IMPORT_MAX_BYTES),
        RouteLimit("POST", re.compile(r"/api/backups/archives"), settings.backup_upload_max_bytes),
    ]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """The live hub (`app.state.live`) listens while the app serves, and so does the
    process's maintenance cache, which ends the live streams when maintenance begins.
    A replace an owner started in this process (`backups/replacing.py`) is cancelled
    when it stops. Uvicorn runs this; apps driven without a lifespan (ASGI tests) have a hub that is
    not running, and `/api/stream` answers 503 there."""
    hub: LiveHub = app.state.live
    cache = maintenance_cache()
    await hub.start(get_database())
    await cache.start(get_database())
    cache.on_start.append(hub.close_all)
    try:
        yield
    finally:
        await replace_runner().stop()
        cache.on_start.remove(hub.close_all)
        await cache.stop()
        await hub.stop()


def create_public_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="to-herd-cats-ai",
        version=app_version(),
        lifespan=_lifespan,
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
    app.add_middleware(MaintenanceMiddleware)  # 503 in maintenance, from the cache alone
    # Swagger UI (outside production only) loads its scripts from a CDN: no API policy.
    docs = () if app.docs_url is None else (app.docs_url,)
    app.add_middleware(SecurityHeadersMiddleware, exempt=docs)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestLogMiddleware)
    install_error_handlers(app)
    configure_tracing(app, settings)
    app.state.live = LiveHub(max_lag_seconds=settings.live_max_lag_seconds)
    app.include_router(api_router())
    app.include_router(collab_relay)  # WebSocket /collab/{page_id}
    app.include_router(mcp_endpoint)  # /mcp: bearer tokens, no CSRF, no cookies

    if settings.environment == "test":
        from app.web.test_routes import router as test_router

        app.include_router(test_router, prefix="/api")
    if settings.static_dir is not None:
        mount_spa(app, settings.static_dir)  # last: it answers every other path
    return app
