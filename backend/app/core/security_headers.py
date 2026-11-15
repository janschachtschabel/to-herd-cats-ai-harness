"""Security headers on every response of the public app: API JSON, errors, OpenAPI, SPA.

- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  same-origin` always (the SPA adds its Content-Security-Policy, which also says
  `frame-ancestors 'none'`).
- `Strict-Transport-Security` only when the request came over https (directly, or from
  a trusted proxy whose `X-Forwarded-Proto` uvicorn applied to the scope); over plain
  http the header means nothing and would pin a local trial to https.

A header the response already set is left as it is.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ALWAYS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}
HSTS = "max-age=31536000"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        https = scope.get("scheme") == "https"

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in ALWAYS.items():
                    if name not in headers:
                        headers[name] = value
                if https and "Strict-Transport-Security" not in headers:
                    headers["Strict-Transport-Security"] = HSTS
            await send(message)

        await self.app(scope, receive, send_wrapper)
