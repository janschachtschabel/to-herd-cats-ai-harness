"""Talking to an OpenID provider (plan M9 decision 12), always through the egress guard
(`core/egress.py`): https only, public addresses or the private hosts and networks the
operator lists in `HERD_OIDC_ALLOWED_HOSTS`, the name resolved and checked when
connecting, no redirects, no proxy from the environment.

- Discovery (OpenID Connect Discovery 1.0, 4): `<issuer>/.well-known/openid-configuration`;
  the document's `issuer` must equal the configured one exactly, and the three
  endpoints this code uses must pass the same rules as a base URL.
- JWKS: a JSON object with a list `keys`.
- The token request: authorization code with the PKCE verifier and the same redirect
  URI, the client authenticated with HTTP Basic (RFC 6749 2.3.1, which every server
  must support) or, without a secret, by `client_id` alone. Only the `id_token` of the
  answer is used; no userinfo call.

Answers are capped (`MAX_ANSWER_BYTES`). Whatever goes wrong becomes a
`ProviderFailure` with a fixed code, never the provider's words or a URL.
"""

import base64
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from app.core import egress
from app.core.config import get_settings
from app.core.egress import EgressBlocked, EgressRules
from app.core.egress_allowance import parse_allowance

RULES = EgressRules(allow_private=False, allow_http=False)
TIMEOUT_SECONDS = 15.0
MAX_ANSWER_BYTES = 256 * 1024
DISCOVERY_PATH = "/.well-known/openid-configuration"


class ProviderFailure(Exception):  # noqa: N818
    """`code`: `oidc.provider_unreachable` (the guard refused, no connection, timeout)
    or `oidc.provider_error` (an answer that is not what OIDC promises);
    discovery adds `oidc.issuer_mismatch`."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class Endpoints:
    authorization: str
    token: str
    jwks_uri: str


@dataclass(frozen=True, slots=True)
class TokenRequest:
    endpoint: str
    client_id: str
    secret: str | None = field(repr=False)
    code: str = field(repr=False)
    verifier: str = field(repr=False)
    redirect_uri: str


def rules() -> EgressRules:
    allowance = parse_allowance(get_settings().oidc_allowed_hosts, "HERD_OIDC_ALLOWED_HOSTS")
    return allowance.rules(RULES)


def check_url(url: str) -> str:
    """The URL if it may be dialled as an endpoint; `ProviderFailure` otherwise."""
    try:
        egress.check_base_url(url, rules())
    except EgressBlocked:
        raise ProviderFailure("oidc.provider_unreachable") from None
    return url


async def discover(issuer: str) -> Endpoints:
    document = await _get_json(check_url(issuer.rstrip("/") + DISCOVERY_PATH))
    if not isinstance(document, dict):
        raise ProviderFailure("oidc.provider_error")
    if document.get("issuer") != issuer:
        raise ProviderFailure("oidc.issuer_mismatch")
    found = [document.get(n) for n in ("authorization_endpoint", "token_endpoint", "jwks_uri")]
    if not all(isinstance(url, str) and url for url in found):
        raise ProviderFailure("oidc.provider_error")
    authorization, token, jwks_uri = (check_url(str(url)) for url in found)
    return Endpoints(authorization, token, jwks_uri)


async def fetch_jwks(uri: str) -> dict[str, Any]:
    document = await _get_json(check_url(uri))
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        raise ProviderFailure("oidc.provider_error")
    return {"keys": [k for k in document["keys"] if isinstance(k, dict)]}


async def exchange_code(request: TokenRequest) -> str:
    """The raw ID token of the answer."""
    form = {
        "grant_type": "authorization_code",
        "code": request.code,
        "redirect_uri": request.redirect_uri,
        "code_verifier": request.verifier,
    }
    headers = {"Accept": "application/json"}
    if request.secret is not None:
        pair = f"{quote(request.client_id, safe='')}:{quote(request.secret, safe='')}"
        headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
    else:
        form["client_id"] = request.client_id
    answer = await _send("POST", check_url(request.endpoint), data=form, headers=headers)
    id_token = answer.get("id_token") if isinstance(answer, dict) else None
    if not isinstance(id_token, str) or not id_token:
        raise ProviderFailure("oidc.provider_error")
    return id_token


async def _get_json(url: str) -> Any:
    return await _send("GET", url, headers={"Accept": "application/json"})


async def _send(method: str, url: str, **kwargs: Any) -> Any:
    try:
        async with egress.client(rules(), timeout=TIMEOUT_SECONDS) as http:
            request = http.build_request(method, url, **kwargs)
            response = await http.send(request, stream=True)
            try:
                raw = await _read_limited(response)
            finally:
                await response.aclose()
    except (EgressBlocked, httpx.HTTPError, OSError):
        raise ProviderFailure("oidc.provider_unreachable") from None
    except ValueError:
        raise ProviderFailure("oidc.provider_error") from None
    if response.status_code != 200:
        raise ProviderFailure("oidc.provider_error")
    try:
        return json.loads(raw)
    except ValueError:
        raise ProviderFailure("oidc.provider_error") from None


async def _read_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_ANSWER_BYTES:
            raise ValueError("answer too large")
        chunks.append(chunk)
    return b"".join(chunks)
