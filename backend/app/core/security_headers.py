"""Security headers on every response of the public app: API JSON, errors, OpenAPI, SPA.

- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  same-origin` always.
- `Content-Security-Policy`: `API_POLICY` (nothing may load, run, frame or be framed)
  on every answer that brings no policy of its own. The SPA's files and attachment
  downloads bring theirs; each of them also says `frame-ancestors`, `object-src` and
  `base-uri 'none'` (ASVS 5.0 V3.4.3, V3.4.6; `test_security_headers_on_every_public_route`).
  Paths in `exempt` (Swagger UI outside production, which loads a CDN) get none.
- `Strict-Transport-Security` only when the request came over https (directly, or from
  a trusted proxy whose `X-Forwarded-Proto` uvicorn applied to the scope); over plain
  http the header means nothing and would pin a local trial to https. It covers
  subdomains (ASVS 5.0 V3.4.1, level 2): the app's own host name, and below it.

A header the response already set is left as it is.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ALWAYS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}
HSTS = "max-age=31536000; includeSubDomains"
API_POLICY = "; ".join(
    [
        "default-src 'none'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, exempt: tuple[str, ...] = ()) -> None:
        self.app = app
        self.exempt = exempt

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        https = scope.get("scheme") == "https"
        policy = not str(scope.get("path", "")).startswith(self.exempt) if self.exempt else True

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in ALWAYS.items():
                    if name not in headers:
                        headers[name] = value
                if policy and "Content-Security-Policy" not in headers:
                    headers["Content-Security-Policy"] = API_POLICY
                if https and "Strict-Transport-Security" not in headers:
                    headers["Strict-Transport-Security"] = HSTS
            await send(message)

        await self.app(scope, receive, send_wrapper)
