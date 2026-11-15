"""`/mcp`: the MCP endpoint for external AI clients (plan M8 decisions 1, 5 and 6).

In this order, before the SDK sees anything:

1. **No browsers.** A request that carries an `Origin` header is refused (403
   `mcp.origin_refused`): MCP clients send none, and a page in a browser (DNS
   rebinding, a token pasted into a site) always does. No CORS headers are sent.
2. **The token**, from `Authorization: Bearer` only, resolved anew on every request
   (`tokens/resolve.py`): whatever is wrong with it answers the same 401
   `token.invalid` with `WWW-Authenticate`; past the token's limit 429
   `mcp.rate_limited` with `Retry-After`. A session cookie opens nothing here.
   The resolver commits (the rate limit), so it runs before anything else writes.
3. **POST only**: no server stream to open (GET) and no session to end (DELETE), 405.
4. The body, at most `HERD_MAX_BODY_BYTES` (413 otherwise), goes to the SDK
   (`app/mcp/server.py`), which answers in JSON-RPC.

Refusals before the SDK come in the MCP form, a JSON-RPC error without an id, with
the house error (code, message, trace id) as its `data`; never an internal detail.
"""

from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.core.errors import RateLimited, Unauthorized, error_body
from app.core.logging import bind_request_fields, log_context
from app.mcp.server import ResponseTooLarge, serve
from app.modules.auth.deps import SessionDep, SettingsDep
from app.modules.mcp_tools.service import McpToolService
from app.modules.tokens.resolve import TokenResolver

router = APIRouter()

PATH = "/mcp"
CHALLENGE = 'Bearer realm="to-herd-cats-ai", error="invalid_token"'
SERVER_ERROR = -32000  # JSON-RPC: implementation-defined server error


def refusal(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": None,
        "error": {
            "code": SERVER_ERROR,
            "message": message,
            "data": error_body(code, message)["error"],
        },
    }
    return JSONResponse(body, status_code=status, headers=headers)


@router.api_route(PATH, methods=["POST", "GET", "DELETE"], include_in_schema=False)
async def mcp_endpoint(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    if "origin" in request.headers:
        return refusal(403, "mcp.origin_refused", "Requests from browsers are not accepted.")
    try:
        token = await TokenResolver(session, settings).resolve(request.headers.get("authorization"))
    except Unauthorized:
        message = "A valid access token is required."
        return refusal(401, "token.invalid", message, {"WWW-Authenticate": CHALLENGE})
    except RateLimited as exc:
        retry = {"Retry-After": str(exc.retry_after)}
        return refusal(429, "mcp.rate_limited", "Too many requests for this token.", retry)
    fields = {"org_id": str(token.actor.org_id), "actor": str(token.actor.principal)}
    bind_request_fields(**fields)
    if request.method != "POST":
        message = "Only POST: this endpoint keeps no sessions and opens no streams."
        return refusal(405, "mcp.method_not_allowed", message, {"Allow": "POST"})
    body = await request.body()  # held to HERD_MAX_BODY_BYTES on the way in
    with log_context(**fields):
        try:
            reply = await serve(
                request.scope, body, McpToolService(session), token, settings.max_body_bytes
            )
        except ResponseTooLarge:
            return refusal(500, "mcp.response_too_large", "The answer was too large.")
    headers = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in reply.headers
        if k.lower() != b"content-length"
    }
    return Response(bytes(reply.body), status_code=reply.status, headers=headers)
