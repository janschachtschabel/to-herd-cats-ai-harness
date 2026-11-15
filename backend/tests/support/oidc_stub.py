"""A local OpenID Connect provider for tests (plan M9: never the real network):
discovery, authorization code with PKCE (S256), the token endpoint answering an ID
token signed with its own key, and the JWKS.

Scriptable through `state` (shared with the test): the registered client
(`client_id`, `client_secret`, HTTP Basic at the token endpoint), `identity` (the
claims of the next sign-in: `sub`, `email`, `email_verified`, `hd`, `name`),
`token_claims` (claims set or, as None, removed in the token, after the identity:
a wrong `aud`, `iss`, `exp`...), `issuer_claim` (the `iss` to put in, e.g.
`accounts.google.com` for the Google preset), `alg_mode` (`normal`, `none`,
`hs256`: a token "signed" with the public key), `discovery_issuer` (the issuer the
discovery document names), `failures` (status codes for the next token requests),
`rotate()` (a new signing key, published next to the old one only after
`publish_rotated()`). `log` keeps the path and the query or form of every request;
`authorize(url)` plays the person who approves and returns the query the browser
brings back.

In tests: the `oidc_stub` fixture (`tests/factories_oidc.py`), https for `idp.test`
in a thread. As a process: `python -m tests.support.oidc_stub --port 8100` (plain
http; with `--certfile`/`--keyfile` https and `--name` for the host name) with
`/_stub/log`, `/_stub/reset`, `/_stub/script` (`{"identity": {...}, ...}`).
"""

import argparse
import base64
import hashlib
import json
import socket
import tempfile
import threading
import time
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

from tests.support.oidc_keys import SigningKey
from tests.support.openai_stub import self_signed

TLS_NAME = "idp.test"
DEFAULT_IDENTITY: dict[str, Any] = {
    "sub": "stub-sub-1",
    "email": "anna@example.com",
    "email_verified": True,
    "name": "Anna Beispiel",
}


@dataclass
class Grant:
    redirect_uri: str
    challenge: str
    nonce: str
    claims: dict[str, Any]


@dataclass
class OidcStubState:
    base: str = ""
    client_id: str = "herd-oidc-client"
    client_secret: str = "oidc-SECRET-value-7"
    identity: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_IDENTITY))
    token_claims: dict[str, Any] = field(default_factory=dict)
    issuer_claim: str | None = None
    discovery_issuer: str | None = None
    alg_mode: str = "normal"
    failures: deque[int] = field(default_factory=deque)
    keys: list[SigningKey] = field(default_factory=lambda: [SigningKey("stub-1")])
    published: int = 1  # how many of `keys` the JWKS shows
    log: list[dict[str, Any]] = field(default_factory=list)
    codes: dict[str, Grant] = field(default_factory=dict)
    counter: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def reset(self) -> None:
        fresh = OidcStubState(base=self.base)
        for name in fresh.__dataclass_fields__:
            if name not in ("lock", "keys"):
                setattr(self, name, getattr(fresh, name))
        self.keys = self.keys[:1]

    def rotate(self) -> None:
        """Sign with a new key; the JWKS shows it only after `publish_rotated`."""
        self.keys.append(SigningKey(f"stub-{len(self.keys) + 1}"))

    def publish_rotated(self) -> None:
        self.published = len(self.keys)

    def requests(self, path: str) -> list[dict[str, Any]]:
        return [r for r in self.log if r["path"] == path]

    def authorize(self, url: str) -> dict[str, str]:
        query = dict(parse_qsl(urlsplit(url).query))
        self.log.append({"path": "/authorize", "query": query})
        assert query["response_type"] == "code", query
        assert query["client_id"] == self.client_id, query
        assert query["code_challenge_method"] == "S256", query
        assert "openid" in query["scope"].split(), query
        with self.lock:
            self.counter += 1
            code = f"code-{self.counter}"
            self.codes[code] = Grant(
                query["redirect_uri"], query["code_challenge"], query["nonce"], dict(self.identity)
            )
        return {"code": code, "state": query["state"]}

    def id_token(self, grant: Grant) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self.issuer_claim or self.base,
            "aud": self.client_id,
            "iat": now,
            "exp": now + 3600,
            "nonce": grant.nonce,
            **grant.claims,
        }
        for name, value in self.token_claims.items():
            if value is None:
                claims.pop(name, None)
            else:
                claims[name] = value
        key = self.keys[-1]
        if self.alg_mode == "none":
            return key.sign_none(claims)
        if self.alg_mode == "hs256":
            return key.sign_hs256_with_public_key(claims)
        return key.sign(claims)


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _client_ok(state: OidcStubState, request: Request) -> bool:
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return False
    user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    return user == state.client_id and password == state.client_secret


def build_app(state: OidcStubState) -> Starlette:
    async def discovery(request: Request) -> Response:
        state.log.append({"path": "/.well-known/openid-configuration"})
        return JSONResponse(
            {
                "issuer": state.discovery_issuer or state.base,
                "authorization_endpoint": f"{state.base}/authorize",
                "token_endpoint": f"{state.base}/token",
                "jwks_uri": f"{state.base}/jwks",
                "response_types_supported": ["code"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "code_challenge_methods_supported": ["S256"],
            }
        )

    async def jwks(request: Request) -> Response:
        state.log.append({"path": "/jwks"})
        return JSONResponse({"keys": [k.jwk() for k in state.keys[: state.published]]})

    async def authorize(request: Request) -> Response:
        query = state.authorize(str(request.url))
        target = dict(parse_qsl(request.url.query))["redirect_uri"]
        return RedirectResponse(f"{target}?{urlencode(query)}", status_code=302)

    async def token(request: Request) -> Response:
        form = dict(parse_qsl((await request.body()).decode()))
        state.log.append({"path": "/token", "form": form, "headers": dict(request.headers)})
        if state.failures:
            return JSONResponse({"error": "scripted"}, status_code=state.failures.popleft())
        if not _client_ok(state, request):
            return JSONResponse({"error": "invalid_client"}, status_code=401)
        grant = state.codes.pop(form.get("code", ""), None)
        if (
            form.get("grant_type") != "authorization_code"
            or grant is None
            or grant.redirect_uri != form.get("redirect_uri")
            or grant.challenge != _challenge(form.get("code_verifier", ""))
        ):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return JSONResponse(
            {
                "access_token": "stub-access",
                "token_type": "Bearer",
                "expires_in": 3600,
                "id_token": state.id_token(grant),
            }
        )

    async def control_log(request: Request) -> Response:
        return JSONResponse(state.log)

    async def control_reset(request: Request) -> Response:
        state.reset()
        return JSONResponse({})

    async def control_script(request: Request) -> Response:
        script = json.loads(await request.body())
        state.failures.extend(script.pop("failures", []))
        if "identity" in script:
            state.identity = {**DEFAULT_IDENTITY, **script.pop("identity")}
        for name, value in script.items():
            if name in OidcStubState.__dataclass_fields__ and name not in ("keys", "lock"):
                setattr(state, name, value)
        return JSONResponse({})

    routes = [
        Route("/.well-known/openid-configuration", discovery, methods=["GET"]),
        Route("/jwks", jwks, methods=["GET"]),
        Route("/authorize", authorize, methods=["GET"]),
        Route("/token", token, methods=["POST"]),
        Route("/_stub/log", control_log, methods=["GET"]),
        Route("/_stub/reset", control_reset, methods=["POST"]),
        Route("/_stub/script", control_script, methods=["POST"]),
    ]
    return Starlette(routes=routes)


class OidcStub:
    """The stub on 127.0.0.1 in a thread of its own, serving https for `TLS_NAME`
    (tests resolve it to 127.0.0.1 through `egress.Network`)."""

    def __init__(self) -> None:
        self.state = OidcStubState()
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

    def start(self) -> "OidcStub":
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
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--certfile", help="serve https with this certificate (PEM)")
    parser.add_argument("--keyfile", help="the certificate's key (PEM)")
    parser.add_argument("--name", help="the host name clients use (default: --host)")
    args = parser.parse_args()
    scheme = "https" if args.certfile else "http"
    state = OidcStubState(base=f"{scheme}://{args.name or args.host}:{args.port}")
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
