"""503 in maintenance (plan M9 decision 9). While the process's cache says the
installation is in maintenance, every request to the API (`/api/...`) and to `/mcp`
is answered 503 `maintenance.active` with `Retry-After: 30` (temporary), except
`GET /api/maintenance` (what the browser's maintenance page asks). The SPA's files
stay reachable, and the probes and metrics live on the internal port. Nothing here
touches the database. WebSockets (`/collab/...`) are refused by the relay itself
(4503, `web/collab_proxy.py`)."""

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import AppError, error_body
from app.modules.maintenance.cache import in_maintenance

CODE = "maintenance.active"
MESSAGE = "The installation is in maintenance; try again shortly."
RETRY_AFTER_SECONDS = 30
STATE_PATH = "/api/maintenance"
_GUARDED = ("/api/", "/mcp/")


class MaintenanceActive(AppError):
    """For routes outside the middleware (the internal collab API)."""

    status_code = 503
    code = CODE
    retry_after: int | None = RETRY_AFTER_SECONDS

    def __init__(self) -> None:
        super().__init__(MESSAGE)


def refuse_in_maintenance() -> None:
    """A route dependency: 503 while in maintenance."""
    if in_maintenance():
        raise MaintenanceActive()


def guarded(method: str, path: str) -> bool:
    """Whether maintenance answers this request with 503."""
    if path == STATE_PATH and method in ("GET", "HEAD"):
        return False
    return path in ("/api", "/mcp") or path.startswith(_GUARDED)


async def answer_maintenance(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=503,
        content=error_body(CODE, MESSAGE),
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )
    await response(scope, receive, send)


class MaintenanceMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and in_maintenance()
            and guarded(scope.get("method", ""), scope.get("path", ""))
        ):
            await answer_maintenance(scope, receive, send)
            return
        await self.app(scope, receive, send)
