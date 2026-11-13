"""`GET /api/stream`: server-sent events for the caller's login session (spec 6.4).

The session is checked when the stream opens (401 without one); the database session
of that check is closed before the first byte is sent, so an open stream holds no
connection of the pool. Then the hub of this process (`live.py`) feeds the stream
until the client goes, the login session ends, or the process stops.

Events: `message.created|updated|deleted`, `reaction.changed`, `notification.created`,
`conversation.read`, `channel.changed`, `activity.changed`, `resync`; their data is
`{"conversation_id", "message_id", "parent_id"}` (ids or null), never content: the
client reloads what it shows through the API, which checks again.
"""

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from app.core.errors import Unauthorized
from app.modules.auth.deps import AuthDep
from app.modules.messaging.live import Connection, LiveHub, LiveUnavailable

live = APIRouter(tags=["live"])

HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


def hub_of(app: FastAPI) -> LiveHub:
    hub = getattr(app.state, "live", None)
    if not isinstance(hub, LiveHub) or not hub.running:
        raise LiveUnavailable()
    return hub


class LiveResponse(StreamingResponse):
    """The stream; however it ends, the hub forgets it."""

    def __init__(self, hub: LiveHub, connection: Connection) -> None:
        super().__init__(connection.frames(), media_type="text/event-stream", headers=HEADERS)
        self.hub = hub
        self.connection = connection

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.hub.disconnect(self.connection)


@live.get(
    "/stream",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Server-sent events"},
        429: {"description": "Too many streams of this login session"},
    },
)
async def stream(request: Request, ctx: AuthDep) -> StreamingResponse:
    hub = hub_of(request.app)
    if ctx.session_id is None:
        raise Unauthorized(code="auth.session_invalid")
    connection = hub.connect(ctx.org_id, ctx.user.id, ctx.session_id)
    return LiveResponse(hub, connection)
