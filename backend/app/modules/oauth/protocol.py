"""Talking to an authorization server (OAuth 2.1 draft, RFC 6749, RFC 7636 PKCE,
RFC 7009 revocation, RFC 8707 resource indicators), always through the egress guard
(`core/egress.py`: https, public addresses or the private hosts the operator lists
in `HERD_MCP_ALLOWED_HOSTS`, the name resolved and checked when connecting, no
redirects; the operator's `HERD_AI_EGRESS_PROXY` if set, except for listed hosts).

- The authorization URL carries `response_type=code`, `client_id`, `redirect_uri`,
  `state`, the S256 `code_challenge`, `scope` and `resource` (when the client names
  them). Never the client secret.
- Token requests are form-encoded with `Accept: application/json` (GitHub answers
  form-encoded without it); the client authenticates with HTTP Basic or in the form
  (`token_auth`), a public client sends only its `client_id`.
- An answer is capped (64 KiB) and must be a JSON object with a bearer
  `access_token`; whatever goes wrong becomes a `TokenStatus`, never the server's
  words (an error body may echo what was sent).
"""

import base64
import hashlib
import json
import secrets as random
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.core import egress
from app.core.config import get_settings
from app.core.egress import EgressBlocked, EgressRules
from app.core.egress_allowance import parse_allowance
from app.modules.ai.provider import egress_proxy
from app.modules.oauth.models import TokenAuth

# Authorization servers: https and public addresses only, plus the private hosts the
# operator lists for MCP servers (`HERD_MCP_ALLOWED_HOSTS`: an in-house GitLab is its
# own authorization server), as for MCP servers.
RULES = EgressRules(allow_private=False, allow_http=False)
TIMEOUT_SECONDS = 20.0
MAX_ANSWER_BYTES = 64 * 1024
MAX_EXPIRES_SECONDS = 10 * 365 * 24 * 3600


class TokenStatus(StrEnum):
    OK = "ok"
    INVALID_GRANT = "invalid_grant"  # the code or refresh token is no longer good
    REJECTED = "rejected"  # any other refusal (4xx): client, scope, request
    BLOCKED = "blocked"  # the egress guard refused the address
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    REDIRECT = "redirect"
    SERVER_ERROR = "server_error"
    INVALID_RESPONSE = "invalid_response"


class TokenFailure(Exception):  # noqa: N818
    def __init__(self, status: TokenStatus) -> None:
        self.status = status
        super().__init__(f"token request failed: {status}")


@dataclass(frozen=True, slots=True)
class ClientCredentials:
    """What the token endpoint needs of a client, copied out of its row with the secret
    resolved (no session is held while the server answers)."""

    client_id: str
    secret: str | None = field(repr=False)
    token_auth: TokenAuth
    token_endpoint: str
    revocation_endpoint: str | None
    resource: str | None


@dataclass(frozen=True, slots=True)
class Tokens:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False)
    expires_in: timedelta | None


def egress_for(url: str) -> tuple[EgressRules, str | None]:
    """The rules and proxy for a request to `url`: a listed private host is dialled
    directly, past an egress proxy meant for the outside."""
    allowance = parse_allowance(get_settings().mcp_allowed_hosts)
    return allowance.rules(RULES), None if allowance.covers(url) else egress_proxy()


def new_state() -> str:
    return random.token_urlsafe(32)


def new_verifier() -> str:
    """43 to 128 unreserved characters (RFC 7636 4.1): here 64."""
    return random.token_urlsafe(48)


def challenge_of(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorization_url(
    endpoint: str,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    verifier: str,
    scopes: str,
    resource: str | None,
) -> str:
    query: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge_of(verifier),
        "code_challenge_method": "S256",
    }
    if scopes:
        query["scope"] = scopes
    if resource:
        query["resource"] = resource
    return f"{endpoint}?{urlencode(query, quote_via=quote)}"


async def exchange_code(
    client: ClientCredentials, *, code: str, verifier: str, redirect_uri: str
) -> Tokens:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    return _tokens(await _post(client, client.token_endpoint, form))


async def refresh(client: ClientCredentials, refresh_token: str) -> Tokens:
    form = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    return _tokens(await _post(client, client.token_endpoint, form))


async def revoke(client: ClientCredentials, token: str, hint: str) -> None:
    """RFC 7009; raises `TokenFailure` if the server did not take it."""
    assert client.revocation_endpoint is not None
    form = {"token": token, "token_type_hint": hint}
    await _post(client, client.revocation_endpoint, form, resource=False)


async def _post(
    client: ClientCredentials, url: str, form: dict[str, str], *, resource: bool = True
) -> Any:
    headers = {"Accept": "application/json"}
    body = dict(form)
    if resource and client.resource:
        body["resource"] = client.resource
    if client.secret is not None and client.token_auth == TokenAuth.BASIC:
        pair = f"{_form_escape(client.client_id)}:{_form_escape(client.secret)}"
        headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
    else:
        body["client_id"] = client.client_id
        if client.secret is not None:
            body["client_secret"] = client.secret
    failure: TokenStatus
    try:
        rules, proxy = egress_for(url)
        async with egress.client(rules, timeout=TIMEOUT_SECONDS, proxy=proxy) as http:
            request = http.build_request("POST", url, data=body, headers=headers)
            response = await http.send(request, stream=True)
            try:
                raw = await read_limited(response)
            finally:
                await response.aclose()
        return _answer(response.status_code, raw)
    except TokenFailure:
        raise
    except EgressBlocked:
        failure = TokenStatus.BLOCKED
    except httpx.TimeoutException:
        failure = TokenStatus.TIMEOUT
    except (httpx.HTTPError, OSError):
        failure = TokenStatus.UNREACHABLE
    except ValueError:
        failure = TokenStatus.INVALID_RESPONSE
    raise TokenFailure(failure) from None


def _form_escape(value: str) -> str:
    """RFC 6749 2.3.1: id and secret are form-encoded before they are joined."""
    return quote(value, safe="")


async def read_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_ANSWER_BYTES:
            raise ValueError("answer too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _answer(status: int, raw: bytes) -> Any:
    if 300 <= status < 400:
        raise TokenFailure(TokenStatus.REDIRECT)
    if status >= 500:
        raise TokenFailure(TokenStatus.SERVER_ERROR)
    if status >= 400:
        error = None
        try:
            parsed = json.loads(raw)
            error = parsed.get("error") if isinstance(parsed, dict) else None
        except ValueError:
            pass
        invalid = status == 400 and error == "invalid_grant"
        raise TokenFailure(TokenStatus.INVALID_GRANT if invalid else TokenStatus.REJECTED)
    if not raw.strip():
        return None
    return json.loads(raw)


def _tokens(answer: Any) -> Tokens:
    if not isinstance(answer, dict):
        raise TokenFailure(TokenStatus.INVALID_RESPONSE)
    access = answer.get("access_token")
    kind = answer.get("token_type", "bearer")
    refresh_token = answer.get("refresh_token")
    expires = answer.get("expires_in")
    if (
        not isinstance(access, str)
        or not access
        or not isinstance(kind, str)
        or kind.lower() != "bearer"
        or (refresh_token is not None and not isinstance(refresh_token, str))
    ):
        raise TokenFailure(TokenStatus.INVALID_RESPONSE)
    if isinstance(expires, str) and expires.isdigit():
        expires = int(expires)  # some servers send it as a string
    lifetime = None
    if isinstance(expires, int) and not isinstance(expires, bool) and expires >= 0:
        lifetime = timedelta(seconds=min(expires, MAX_EXPIRES_SECONDS))
    return Tokens(access, refresh_token or None, lifetime)
