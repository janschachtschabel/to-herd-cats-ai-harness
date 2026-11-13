"""The guard on outbound HTTP (plan M5 decision 7; spec 11: every server-side call to
a URL someone configured goes through it).

- Schemes: `https`; `http` too where the rules allow it (connections of kind `local`).
- A base URL carries no credentials, query or fragment (`check_base_url`, at write).
- Addresses: link-local, metadata, unspecified, multicast and reserved addresses are
  never dialled; other non-global addresses (private, loopback, CGNAT, ULA) only where
  the rules allow private targets. IPv6 forms that embed an IPv4 address (mapped,
  compatible, 6to4, NAT64) are judged by that address.
- The name is resolved when the connection is made, inside the HTTP client
  (`GuardedBackend`), and the connection goes to exactly the address checked: a DNS
  answer that changes between a check and the call (rebinding) cannot slip through,
  because there is no separate check. TLS still verifies the name in the URL (SNI).
- Redirects are never followed; proxy and other settings from the environment are
  ignored (a proxy would dial on our behalf, past the guard).

Tests point the guard at a local stub through `Network` (resolver, trusted TLS
context, extra allowed networks), handed in or set as the module's `_network`; there
is no setting that loosens the rules.
"""

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx

type IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
type IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
type Resolver = Callable[[str, int], Awaitable[list[str]]]

_NEVER: tuple[IPNetwork, ...] = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "169.254.0.0/16",  # link-local, cloud metadata (169.254.169.254)
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved, broadcast
        "100.100.100.200/32",  # Alibaba metadata
        "168.63.129.16/32",  # Azure host endpoint
        "::/128",
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
        "fd00:ec2::254/128",  # AWS metadata over IPv6
    )
)
_NAT64 = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("64:ff9b:1::/48"))
_COMPATIBLE = ipaddress.ip_network("::/96")


class EgressBlocked(Exception):  # noqa: N818 (a verdict, not an error class name)
    """The guard refused the target; `reason` is a fixed word, never the target."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"egress blocked: {reason}")


@dataclass(frozen=True, slots=True)
class EgressRules:
    allow_private: bool
    allow_http: bool


async def _system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


@dataclass(frozen=True, slots=True)
class Network:
    """How names are resolved and TLS is verified; tests hand in their own."""

    resolver: Resolver = _system_resolver
    ssl_context: ssl.SSLContext | None = None
    extra_allowed: tuple[IPNetwork, ...] = field(default=())


_network = Network()


def embedded_ipv4(address: IPAddress) -> ipaddress.IPv4Address | None:
    if isinstance(address, ipaddress.IPv4Address):
        return None
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    if address.sixtofour is not None:
        return address.sixtofour
    if any(address in net for net in _NAT64):
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    if address in _COMPATIBLE and int(address) > 1:
        return ipaddress.IPv4Address(int(address))
    return None


def check_address(
    address: IPAddress, rules: EgressRules, extra_allowed: Iterable[IPNetwork] = ()
) -> None:
    """Raise unless the rules allow dialling `address`."""
    judged: IPAddress = embedded_ipv4(address) or address
    for candidate in {address, judged}:
        if any(candidate.version == n.version and candidate in n for n in _NEVER):
            raise EgressBlocked("blocked_address")
    if any(judged.version == n.version and judged in n for n in extra_allowed):
        return
    if not judged.is_global and not rules.allow_private:
        raise EgressBlocked("private_address")


def check_base_url(url: str, rules: EgressRules) -> str:
    """The URL without a trailing slash, if the rules allow it as a base URL; checks
    literal addresses and `localhost` names here (names are checked when dialled)."""
    if any(c.isspace() or not c.isprintable() for c in url):
        raise EgressBlocked("url")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise EgressBlocked("url") from None
    schemes = {"https", "http"} if rules.allow_http else {"https"}
    if parts.scheme not in schemes:
        raise EgressBlocked("scheme")
    host = parts.hostname
    if not host or "@" in parts.netloc or parts.query or parts.fragment or "?" in url:
        raise EgressBlocked("url")
    bare = host.rstrip(".")
    if bare == "localhost" or bare.endswith(".localhost"):
        if not rules.allow_private:
            raise EgressBlocked("private_address")
    elif (literal := _literal(host)) is not None:
        check_address(literal, rules)
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc += f":{port}"
    return f"{parts.scheme}://{netloc}{parts.path.rstrip('/')}"


def _literal(host: str) -> IPAddress | None:
    """An address written as such, also in the old forms `getaddrinfo` still accepts
    (`2130706433`, `0x7f.1`, `0177.0.0.1`)."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None


class GuardedBackend(httpcore.AsyncNetworkBackend):
    """Resolves, checks every answer, and dials only a checked address."""

    def __init__(
        self,
        rules: EgressRules,
        network: Network,
        inner: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self.rules = rules
        self.network = network
        self.inner = inner or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore's interface)
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await self._resolve(host, port, timeout)
        failure: httpcore.ConnectError | None = None
        for address in addresses:
            try:
                return await self.inner.connect_tcp(
                    str(address), port, timeout, local_address, socket_options
                )
            except httpcore.ConnectError as exc:
                failure = exc
        assert failure is not None
        raise failure

    async def _resolve(self, host: str, port: int, seconds: float | None) -> list[IPAddress]:
        try:
            async with asyncio.timeout(seconds):
                answers = await self.network.resolver(host, port)
        except TimeoutError:
            raise httpcore.ConnectTimeout("name resolution timed out") from None
        except OSError:
            raise httpcore.ConnectError("name resolution failed") from None
        addresses: list[IPAddress] = []
        for answer in answers:
            try:
                address = ipaddress.ip_address(answer)
            except ValueError:
                raise EgressBlocked("unresolvable") from None
            check_address(address, self.rules, self.network.extra_allowed)
            if address not in addresses:
                addresses.append(address)
        if not addresses:
            raise EgressBlocked("unresolvable")
        return addresses

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore's interface)
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise EgressBlocked("scheme")

    async def sleep(self, seconds: float) -> None:
        await self.inner.sleep(seconds)


class _GuardedTransport(httpx.AsyncHTTPTransport):
    def __init__(self, rules: EgressRules, network: Network) -> None:
        context = network.ssl_context or httpx.create_ssl_context(trust_env=True)
        super().__init__(verify=context, trust_env=False)
        # httpx takes no network backend; its pool does. Our pool replaces the one built
        # above (no connection made yet); test_egress proves the guard is in the path.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=context,
            network_backend=GuardedBackend(rules, network),
            max_connections=20,
            max_keepalive_connections=5,
        )
        self.rules = rules

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        schemes = {"https", "http"} if self.rules.allow_http else {"https"}
        if request.url.scheme not in schemes:
            raise EgressBlocked("scheme")
        return await super().handle_async_request(request)


def client(
    rules: EgressRules, *, timeout: float, network: Network | None = None
) -> httpx.AsyncClient:
    """An HTTP client whose every connection goes through the guard."""
    return httpx.AsyncClient(
        transport=_GuardedTransport(rules, network or _network),
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )
