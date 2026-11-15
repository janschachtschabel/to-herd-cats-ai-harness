"""Finding an MCP server's authorization server, as MCP's authorization (2025-11-25)
asks of a client: a proposal for an OAuth client the admin still saves (and
registers at the provider; there is no dynamic client registration here).

1. The server is asked without a token; a 401 whose `WWW-Authenticate` names
   `resource_metadata` (RFC 9728 5.1) points at its protected resource metadata,
   and its `scope` is the scope to ask for.
2. Otherwise the well-known URIs: path-inserted
   (`/.well-known/oauth-protected-resource/<path>`), then at the root.
3. The metadata's `resource` must be the server's address (RFC 9728 3.3), else the
   proposal is refused (`resource_mismatch`); its first authorization server is used.
4. That server's metadata: RFC 8414 with path insertion, OpenID discovery with path
   insertion, OpenID discovery appended (for an issuer without a path: RFC 8414,
   then OpenID). `pkce` says whether it announces S256 (MCP clients refuse servers
   that do not; the admin decides, and the flow always sends S256).

Every request goes through the egress guard (https, public addresses), each answer
capped at 64 KiB; every address found must pass the same rules as a written one.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core import egress
from app.core.egress import EgressBlocked
from app.modules.oauth.protocol import egress_for, read_limited

TIMEOUT_SECONDS = 10.0
_PROBE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "to-herd-cats-ai", "version": "1"},
    },
}
_PARAM = re.compile(r'([A-Za-z_]+)\s*=\s*"([^"]*)"')


class DiscoveryStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    NO_METADATA = "no_metadata"  # no protected resource metadata found
    RESOURCE_MISMATCH = "resource_mismatch"
    NO_AUTHORIZATION_SERVER = "no_authorization_server"
    INVALID_METADATA = "invalid_metadata"  # an endpoint missing or not allowed


@dataclass
class Discovery:
    status: DiscoveryStatus
    resource: str | None = None
    issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    revocation_endpoint: str | None = None
    scopes: str = ""
    pkce: bool = False
    registration: bool = False


class _Stop(Exception):  # noqa: N818
    def __init__(self, status: DiscoveryStatus) -> None:
        self.status = status


async def discover(url: str) -> Discovery:
    """`url` has passed `egress.check_base_url(url, RULES)`."""
    try:
        rules, proxy = egress_for(url)
        async with egress.client(rules, timeout=TIMEOUT_SECONDS, proxy=proxy) as http:
            return await _discover(http, url)
    except _Stop as stop:
        return Discovery(stop.status)
    except EgressBlocked:
        return Discovery(DiscoveryStatus.BLOCKED)
    except httpx.TimeoutException:
        return Discovery(DiscoveryStatus.TIMEOUT)
    except (httpx.HTTPError, OSError):
        return Discovery(DiscoveryStatus.UNREACHABLE)


async def _discover(http: httpx.AsyncClient, url: str) -> Discovery:
    pointed, challenged_scope = await _challenge(http, url)
    candidates = [pointed] if pointed else _resource_candidates(url)
    metadata = await _first(http, candidates, lambda m: isinstance(m.get("resource"), str))
    if metadata is None:
        raise _Stop(DiscoveryStatus.NO_METADATA)
    resource = metadata["resource"]
    if _canonical(resource) != _canonical(url):
        return Discovery(DiscoveryStatus.RESOURCE_MISMATCH, resource=resource)
    servers = metadata.get("authorization_servers")
    if not isinstance(servers, list) or not servers or not isinstance(servers[0], str):
        return Discovery(DiscoveryStatus.NO_AUTHORIZATION_SERVER, resource=resource)
    issuer = servers[0]
    _allowed(issuer)
    server = await _first(
        http,
        _server_candidates(issuer),
        lambda m: (
            isinstance(m.get("authorization_endpoint"), str)
            and isinstance(m.get("token_endpoint"), str)
        ),
    )
    if server is None:
        return Discovery(DiscoveryStatus.NO_AUTHORIZATION_SERVER, resource=resource)
    endpoints = {
        name: server.get(name)
        for name in ("authorization_endpoint", "token_endpoint", "revocation_endpoint")
    }
    for value in endpoints.values():
        if value is not None and (not isinstance(value, str) or not _ok(value)):
            return Discovery(DiscoveryStatus.INVALID_METADATA, resource=resource, issuer=issuer)
    supported = metadata.get("scopes_supported")
    scopes = challenged_scope
    if scopes is None and isinstance(supported, list):
        scopes = " ".join(s for s in supported if isinstance(s, str))
    methods = server.get("code_challenge_methods_supported")
    return Discovery(
        DiscoveryStatus.OK,
        resource=resource,
        issuer=issuer,
        authorization_endpoint=endpoints["authorization_endpoint"],
        token_endpoint=endpoints["token_endpoint"],
        revocation_endpoint=endpoints["revocation_endpoint"],
        scopes=scopes or "",
        pkce=isinstance(methods, list) and "S256" in methods,
        registration=isinstance(server.get("registration_endpoint"), str),
    )


async def _challenge(http: httpx.AsyncClient, url: str) -> tuple[str | None, str | None]:
    """The resource metadata URL and scope a 401 names, if the server sends one."""
    headers = {"Accept": "application/json, text/event-stream"}
    request = http.build_request("POST", url, json=_PROBE, headers=headers)
    response = await http.send(request, stream=True)
    await response.aclose()  # the body is not read
    if response.status_code != 401:
        return None, None
    params = dict(_PARAM.findall(response.headers.get("www-authenticate", "")))
    pointed = params.get("resource_metadata")
    if pointed is not None and not _ok(pointed):
        pointed = None
    return pointed, params.get("scope")


def _resource_candidates(url: str) -> list[str]:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/")
    root = f"{origin}/.well-known/oauth-protected-resource"
    return [f"{root}{path}", root] if path else [root]


def _server_candidates(issuer: str) -> list[str]:
    parts = urlsplit(issuer)
    origin = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/")
    if not path:
        return [
            f"{origin}/.well-known/oauth-authorization-server",
            f"{origin}/.well-known/openid-configuration",
        ]
    return [
        f"{origin}/.well-known/oauth-authorization-server{path}",
        f"{origin}/.well-known/openid-configuration{path}",
        f"{origin}{path}/.well-known/openid-configuration",
    ]


async def _first(http: httpx.AsyncClient, urls: list[str], fits: Any) -> dict[str, Any] | None:
    for url in urls:
        _allowed(url)
        request = http.build_request("GET", url, headers={"Accept": "application/json"})
        response = await http.send(request, stream=True)
        try:
            if response.status_code != 200:
                continue
            try:
                parsed = json.loads(await read_limited(response))
            except ValueError:  # too large, not UTF-8, not JSON
                continue
        finally:
            await response.aclose()
        if isinstance(parsed, dict) and fits(parsed):
            return parsed
    return None


def _ok(url: str) -> bool:
    try:
        egress.check_base_url(url, egress_for(url)[0])
    except EgressBlocked:
        return False
    return True


def _allowed(url: str) -> None:
    if not _ok(url):
        raise _Stop(DiscoveryStatus.BLOCKED)


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path.rstrip('/')}"
