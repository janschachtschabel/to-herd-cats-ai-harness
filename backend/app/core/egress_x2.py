"""The egress guard for `httpx2`, the HTTP library the OpenAI SDK under Pydantic AI
uses (the model calls of the agent loop). The same rules as `egress.client`, from the
same checks: the name resolved when connecting, every answer checked, only checked
addresses dialled (`checked_addresses`); the scheme and literal addresses checked per
request (`check_request_target`); no redirects, nothing from the environment; the
operator's proxy (`HERD_AI_EGRESS_PROXY`) only for connections that are not `local`.

A response body larger than MAX_RESPONSE_BYTES ends the call (`ResponseTooLarge`):
a provider cannot fill the worker's memory.
"""

from collections.abc import AsyncIterator, Iterable
from typing import Any

import httpcore2
import httpx2

from app.core import egress
from app.core.egress import (
    EgressBlocked,
    EgressRules,
    Network,
    check_request_target,
    checked_addresses,
)
from app.core.egress_proxy import proxy_for

MAX_RESPONSE_BYTES = 2 * 1024 * 1024

__all__ = ["EgressBlocked", "ResponseTooLarge", "client"]


class ResponseTooLarge(httpx2.TransportError):
    """The provider's answer was larger than MAX_RESPONSE_BYTES."""


class GuardedBackend(httpcore2.AsyncNetworkBackend):
    """Resolves, checks every answer, and dials only a checked address."""

    def __init__(
        self,
        rules: EgressRules,
        network: Network,
        inner: httpcore2.AsyncNetworkBackend | None = None,
    ) -> None:
        self.rules = rules
        self.network = network
        self.inner = inner or httpcore2.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore2's interface)
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        addresses = await checked_addresses(
            self.rules,
            self.network,
            host,
            port,
            timeout,
            httpcore2.ConnectTimeout,
            httpcore2.ConnectError,
        )
        failure: httpcore2.ConnectError | None = None
        for address in addresses:
            try:
                return await self.inner.connect_tcp(
                    str(address), port, timeout, local_address, socket_options
                )
            except httpcore2.ConnectError as exc:
                failure = exc
        assert failure is not None
        raise failure

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore2's interface)
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        raise EgressBlocked("scheme")

    async def sleep(self, seconds: float) -> None:
        await self.inner.sleep(seconds)


class _Limited(httpx2.AsyncByteStream):
    def __init__(self, inner: httpx2.AsyncByteStream) -> None:
        self.inner = inner

    async def __aiter__(self) -> AsyncIterator[bytes]:
        size = 0
        async for chunk in self.inner:
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge("response too large")
            yield chunk

    async def aclose(self) -> None:
        await self.inner.aclose()


class _GuardedTransport(httpx2.AsyncHTTPTransport):
    def __init__(self, rules: EgressRules, network: Network, proxy: str | None) -> None:
        context = network.ssl_context or httpx2.create_ssl_context(trust_env=True)
        super().__init__(verify=context, trust_env=False)
        target = proxy_for(rules, proxy)
        # As in `egress`: the pool built above (no connection made yet) is replaced.
        self._pool: httpcore2.AsyncConnectionPool = (
            httpcore2.AsyncHTTPProxy(
                proxy_url=target.url,
                proxy_auth=target.auth,
                ssl_context=context,
                max_connections=20,
                max_keepalive_connections=5,
            )
            if target is not None
            else httpcore2.AsyncConnectionPool(
                ssl_context=context,
                network_backend=GuardedBackend(rules, network),
                max_connections=20,
                max_keepalive_connections=5,
            )
        )
        self.rules = rules

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        check_request_target(request.url.scheme, request.url.host, self.rules)
        response = await super().handle_async_request(request)
        assert isinstance(response.stream, httpx2.AsyncByteStream)
        response.stream = _Limited(response.stream)
        return response


def client(
    rules: EgressRules,
    *,
    timeout: float,
    network: Network | None = None,
    proxy: str | None = None,
) -> httpx2.AsyncClient:
    """An httpx2 client whose every connection goes through the guard (or the
    operator's proxy, see the module docstring)."""
    return httpx2.AsyncClient(
        transport=_GuardedTransport(rules, network or egress._network, proxy),
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )
