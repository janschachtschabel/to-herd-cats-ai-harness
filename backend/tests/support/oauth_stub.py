"""A local OAuth 2 authorization server for tests (plan M8: never the real network):
authorization code with PKCE (S256 only), refresh with rotation, revocation (RFC 7009)
and metadata (RFC 8414), plus protected resource metadata (RFC 9728) for an MCP
endpoint, so discovery can be tested too.

Scriptable through `state` (shared with the test): the registered client
(`client_id`, `client_secret`, `token_auth`: `client_secret_basic`,
`client_secret_post` or `none`), `expires_in` (None: no expiry in the answer),
`rotate` (a refresh issues a new refresh token and retires the old one, as GitHub
does), `issue_refresh`, `delay` (seconds before a token answer, for races),
`failures` (status codes for the next token requests), `pkce_in_metadata`. Every
request to the token and revocation endpoints is logged with headers and form
(`log`), so a test asserts what went over the wire without our code logging it.

`authorize(url)` plays the person who approves: it checks the authorization request
as the server would and returns the query the browser brings back to the callback.
The same logic answers `GET /authorize` with a redirect (for a browser in e2e).

In tests: the `oauth_stub` fixture (`tests/factories_oauth.py`) runs it with TLS for
`oauth.test` in a thread; as a process: `python -m tests.support.oauth_stub --port
8099` (plain http; with `--certfile`/`--keyfile` https, and `--name` for the host
name its metadata names) with `/_stub/log`, `/_stub/reset`, `/_stub/script`.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import socket
import tempfile
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from tests.support.openai_stub import self_signed

TLS_NAME = "oauth.test"


@dataclass
class Grant:
    client_id: str
    redirect_uri: str
    challenge: str
    scope: str
    resource: str | None


@dataclass
class LoggedRequest:
    path: str
    headers: dict[str, str]
    form: dict[str, str]


@dataclass
class OAuthStubState:
    base: str = ""
    client_id: str = "herd-client"
    client_secret: str | None = "client-SECRET-value-42"
    token_auth: str = "client_secret_post"
    expires_in: int | None = 3600
    rotate: bool = True
    issue_refresh: bool = True
    delay: float = 0.0
    pkce_in_metadata: bool = True
    # `POST /mcp` answers 401 with `WWW-Authenticate: Bearer resource_metadata=...` (to
    # `/meta/prm`) and this scope; False: 404, so discovery falls back to well-known URIs.
    challenge: bool = False
    challenge_scope: str = "mcp"
    resource_override: str | None = None
    # RFC 9207: the `iss` the authorization response carries (None: none), and whether
    # the metadata promise it (`authorization_response_iss_parameter_supported`).
    iss: str | None = None
    iss_in_metadata: bool = False
    failures: deque[int] = field(default_factory=deque)
    log: list[LoggedRequest] = field(default_factory=list)
    codes: dict[str, Grant] = field(default_factory=dict)
    refresh: dict[str, Grant] = field(default_factory=dict)
    issued: list[str] = field(default_factory=list)
    revoked: list[str] = field(default_factory=list)
    counter: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def reset(self) -> None:
        fresh = OAuthStubState(base=self.base)
        for name in fresh.__dataclass_fields__:
            if name != "lock":
                setattr(self, name, getattr(fresh, name))

    def texts(self) -> str:
        return "\n".join(f"{r.path} {r.headers} {r.form}" for r in self.log)

    def token_requests(self, grant: str) -> list[LoggedRequest]:
        return [r for r in self.log if r.path == "/token" and r.form.get("grant_type") == grant]

    def authorize(self, url: str) -> dict[str, str]:
        """The query the browser brings back to the redirect URI after approval."""
        query = dict(parse_qsl(urlsplit(url).query))
        assert query["response_type"] == "code", query
        assert query["client_id"] == self.client_id, query
        assert query["code_challenge_method"] == "S256", query
        assert len(query["code_challenge"]) == 43, query
        with self.lock:
            self.counter += 1
            code = f"code-{self.counter}"
            self.codes[code] = Grant(
                self.client_id,
                query["redirect_uri"],
                query["code_challenge"],
                query.get("scope", ""),
                query.get("resource"),
            )
        answer = {"code": code, "state": query["state"]}
        if self.iss is not None:
            answer["iss"] = self.iss
        return answer

    def _new_tokens(self, grant: Grant) -> dict[str, Any]:
        with self.lock:
            self.counter += 1
            access = f"at-{self.counter}"
            self.issued.append(access)
            body: dict[str, Any] = {"access_token": access, "token_type": "Bearer"}
            if self.expires_in is not None:
                body["expires_in"] = self.expires_in
            if self.issue_refresh:
                body["refresh_token"] = f"rt-{self.counter}"
                self.refresh[body["refresh_token"]] = grant
            if grant.scope:
                body["scope"] = grant.scope
        return body


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _client_ok(state: OAuthStubState, request: Request, form: dict[str, str]) -> bool:
    if state.token_auth == "client_secret_basic":
        header = request.headers.get("authorization", "")
        if not header.startswith("Basic "):
            return False
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
        return user == state.client_id and password == state.client_secret
    if form.get("client_id") != state.client_id:
        return False
    if state.token_auth == "client_secret_post":
        return form.get("client_secret") == state.client_secret
    return "client_secret" not in form


def _error(code: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": code, "error_description": "stub says no"}, status_code=status)


def build_app(state: OAuthStubState) -> Starlette:
    async def logged(request: Request) -> dict[str, str]:
        form = dict(parse_qsl((await request.body()).decode()))
        state.log.append(LoggedRequest(request.url.path, dict(request.headers), form))
        return form

    async def token(request: Request) -> Response:
        form = await logged(request)
        if state.delay:
            await asyncio.sleep(state.delay)
        if state.failures:
            return _error("scripted", state.failures.popleft())
        if request.headers.get("content-type") != "application/x-www-form-urlencoded":
            return _error("invalid_request")
        if not _client_ok(state, request, form):
            return _error("invalid_client", 401)
        kind = form.get("grant_type")
        if kind == "authorization_code":
            grant = state.codes.pop(form.get("code", ""), None)
            if (
                grant is None
                or grant.redirect_uri != form.get("redirect_uri")
                or grant.challenge != _challenge(form.get("code_verifier", ""))
                or grant.resource != form.get("resource")
            ):
                return _error("invalid_grant")
            return JSONResponse(state._new_tokens(grant))
        if kind == "refresh_token":
            presented = form.get("refresh_token", "")
            grant = state.refresh.get(presented)
            if grant is None:
                return _error("invalid_grant")
            if state.rotate:
                del state.refresh[presented]
            body = state._new_tokens(grant)
            if not state.rotate:
                state.refresh.pop(body.get("refresh_token", ""), None)
                body.pop("refresh_token", None)
            return JSONResponse(body)
        return _error("unsupported_grant_type")

    async def revoke(request: Request) -> Response:
        form = await logged(request)
        if not _client_ok(state, request, form):
            return _error("invalid_client", 401)
        state.revoked.append(form.get("token", ""))
        state.refresh.pop(form.get("token", ""), None)
        return Response(status_code=200)

    async def authorize(request: Request) -> Response:
        query = state.authorize(str(request.url))
        target = dict(parse_qsl(request.url.query))["redirect_uri"]
        return RedirectResponse(f"{target}?{urlencode(query)}", status_code=302)

    async def metadata(request: Request) -> Response:
        body: dict[str, Any] = {
            "issuer": state.base,
            "authorization_endpoint": f"{state.base}/authorize",
            "token_endpoint": f"{state.base}/token",
            "revocation_endpoint": f"{state.base}/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "scopes_supported": ["mcp", "read"],
        }
        if state.pkce_in_metadata:
            body["code_challenge_methods_supported"] = ["S256"]
        if state.iss_in_metadata:
            body["authorization_response_iss_parameter_supported"] = True
        return JSONResponse(body)

    async def resource_metadata(request: Request) -> Response:
        body = {
            "resource": state.resource_override or f"{state.base}/mcp",
            "authorization_servers": [state.base],
            "scopes_supported": ["mcp"],
        }
        return JSONResponse(body)

    async def mcp(request: Request) -> Response:
        if not state.challenge:
            return Response(status_code=404)
        header = (
            f'Bearer resource_metadata="{state.base}/meta/prm", scope="{state.challenge_scope}"'
        )
        return Response(status_code=401, headers={"WWW-Authenticate": header})

    async def control_log(request: Request) -> Response:
        return JSONResponse([r.__dict__ for r in state.log])

    async def control_reset(request: Request) -> Response:
        state.reset()
        return JSONResponse({})

    async def control_script(request: Request) -> Response:
        script = json.loads(await request.body())
        state.failures.extend(script.pop("failures", []))
        for name, value in script.items():
            if name in OAuthStubState.__dataclass_fields__:
                setattr(state, name, value)
        return JSONResponse({})

    routes = [
        Route("/authorize", authorize, methods=["GET"]),
        Route("/token", token, methods=["POST"]),
        Route("/revoke", revoke, methods=["POST"]),
        Route("/.well-known/oauth-authorization-server", metadata, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource/mcp", resource_metadata, methods=["GET"]),
        Route("/meta/prm", resource_metadata, methods=["GET"]),
        Route("/mcp", mcp, methods=["POST"]),
        Route("/_stub/log", control_log, methods=["GET"]),
        Route("/_stub/reset", control_reset, methods=["POST"]),
        Route("/_stub/script", control_script, methods=["POST"]),
    ]
    return Starlette(routes=routes)


class OAuthStub:
    """The stub on 127.0.0.1 in a thread of its own, serving https for `TLS_NAME`
    (tests resolve it to 127.0.0.1 through `egress.Network`)."""

    def __init__(self) -> None:
        self.state = OAuthStubState()
        self._dir = tempfile.TemporaryDirectory()
        self.cert_path, key_path = self_signed(Path(self._dir.name), [TLS_NAME])
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self.port: int = self._socket.getsockname()[1]
        self.state.base = self.url
        config = uvicorn.Config(
            build_app(self.state),
            log_config=None,
            log_level=None,
            access_log=False,
            ssl_certfile=str(self.cert_path),
            ssl_keyfile=str(key_path),
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True
        )

    @property
    def url(self) -> str:
        return f"https://{TLS_NAME}:{self.port}"

    def start(self) -> "OAuthStub":
        self._thread.start()
        for _ in range(500):
            if self._server.started:
                return self
            threading.Event().wait(0.01)
        raise RuntimeError("stub did not start")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
        self._socket.close()
        self._dir.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--certfile", help="serve https with this certificate (PEM)")
    parser.add_argument("--keyfile", help="the certificate's key (PEM)")
    parser.add_argument("--name", help="the host name clients use (default: --host)")
    args = parser.parse_args()
    scheme = "https" if args.certfile else "http"
    state = OAuthStubState(base=f"{scheme}://{args.name or args.host}:{args.port}")
    uvicorn.run(
        build_app(state),
        host=args.host,
        port=args.port,
        log_level="warning",
        ssl_certfile=args.certfile,
        ssl_keyfile=args.keyfile,
    )


if __name__ == "__main__":
    main()
