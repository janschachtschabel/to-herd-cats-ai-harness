"""The egress guard for model calls (`core/egress_x2.py`, httpx2 under the OpenAI SDK):
the same rules as `egress.client` (review focus 5), a cap on response size, and the
operator's explicit proxy (ruling M5 (a)) while ambient proxy variables stay ignored."""

import asyncio
from collections.abc import AsyncIterator, Sequence

import httpcore2
import httpx2
import pytest

from app.core import egress, egress_x2
from app.core.egress import EgressBlocked, EgressRules, Network
from app.core.egress_proxy import ProxyTarget
from tests.support.openai_stub import OpenAIStub

EXTERNAL = EgressRules(allow_private=False, allow_http=False)
LOCAL = EgressRules(allow_private=True, allow_http=True)


class _Recorder(httpcore2.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):  # type: ignore[no-untyped-def]  # noqa: ASYNC109
        self.hosts.append(host)
        raise httpcore2.ConnectError("recorded")


def _resolver(*answers: Sequence[str]):  # type: ignore[no-untyped-def]
    queue = list(answers)

    async def resolve(host: str, port: int) -> list[str]:
        return list(queue.pop(0) if len(queue) > 1 else queue[0])

    return resolve


async def test_only_checked_addresses_are_dialled_also_after_a_dns_change() -> None:
    recorder = _Recorder()
    resolve = _resolver(["93.184.216.34"], ["169.254.169.254"])
    backend = egress_x2.GuardedBackend(EXTERNAL, Network(resolver=resolve), inner=recorder)
    with pytest.raises(httpcore2.ConnectError):
        await backend.connect_tcp("api.example.com", 443)
    with pytest.raises(EgressBlocked):
        await backend.connect_tcp("api.example.com", 443)
    assert recorder.hosts == ["93.184.216.34"]


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:9/v1/models",
        "https://[::ffff:127.0.0.1]:9/v1/models",
        "https://[fe80::1]:9/v1/models",
        "http://api.example.com/v1/models",
    ],
)
async def test_an_external_client_refuses_private_targets_and_plain_http(url: str) -> None:
    async with egress_x2.client(EXTERNAL, timeout=5) as client:
        with pytest.raises(EgressBlocked):
            await client.get(url)


async def test_a_local_client_reaches_the_stub_and_ignores_proxy_variables(
    openai_stub: OpenAIStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.invalid:3128")
    async with egress_x2.client(LOCAL, timeout=5) as client:
        response = await client.get(openai_stub.base_url + "/models")
    assert response.status_code == 200


async def test_metadata_addresses_stay_blocked_for_local_clients() -> None:
    async with egress_x2.client(LOCAL, timeout=5) as client:
        with pytest.raises(EgressBlocked):
            await client.get("http://169.254.169.254/latest/meta-data")


async def test_redirects_are_not_followed(openai_stub: OpenAIStub) -> None:
    openai_stub.state.redirect_to = "http://169.254.169.254/latest/meta-data"
    async with egress_x2.client(LOCAL, timeout=5) as client:
        response = await client.get(openai_stub.base_url + "/models")
    assert response.status_code == 302
    assert len(openai_stub.state.log) == 1


async def test_tls_verifies_the_name_in_the_url(
    openai_tls_stub: OpenAIStub, stub_network: Network
) -> None:
    async with egress_x2.client(EXTERNAL, timeout=5, network=stub_network) as client:
        assert (await client.get(openai_tls_stub.base_url + "/models")).status_code == 200
        with pytest.raises(httpx2.ConnectError):
            await client.get(openai_tls_stub.base_url.replace("provider.test", "other.test"))


async def test_a_response_larger_than_the_cap_ends_the_call(
    openai_stub: OpenAIStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    openai_stub.state.models = [f"model-{i:06d}" for i in range(400)]
    monkeypatch.setattr(egress_x2, "MAX_RESPONSE_BYTES", 1000)
    async with egress_x2.client(LOCAL, timeout=5) as client:
        with pytest.raises(egress_x2.ResponseTooLarge):
            await client.get(openai_stub.base_url + "/models")


class _ConnectProxy:
    """A CONNECT proxy on 127.0.0.1 that records its targets and tunnels `*.test` names
    to 127.0.0.1, as a proxy with its own DNS would."""

    def __init__(self) -> None:
        self.targets: list[str] = []
        self.auth: list[str] = []
        self.server: asyncio.Server | None = None

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        return int(self.server.sockets[0].getsockname()[1])

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        target = head.split()[1]
        self.targets.append(target)
        self.auth += [line for line in head.split("\r\n") if line.lower().startswith("proxy-auth")]
        host, port = target.rsplit(":", 1)
        upstream_r, upstream_w = await asyncio.open_connection(
            "127.0.0.1" if host.endswith(".test") else host, int(port)
        )
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()

        async def pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
            try:
                while data := await src.read(65536):
                    dst.write(data)
                    await dst.drain()
            finally:
                dst.close()

        await asyncio.gather(pipe(reader, upstream_w), pipe(upstream_r, writer))


@pytest.fixture
async def connect_proxy() -> AsyncIterator[tuple[_ConnectProxy, int]]:
    proxy = _ConnectProxy()
    port = await proxy.start()
    yield proxy, port
    assert proxy.server is not None
    proxy.server.close()


async def test_the_operators_proxy_carries_external_calls(
    openai_tls_stub: OpenAIStub,
    stub_network: Network,
    connect_proxy: tuple[_ConnectProxy, int],
) -> None:
    """The guard's resolver is not asked (the proxy resolves); the call reaches the
    provider through the proxy, with the proxy's credentials only towards the proxy."""
    proxy, port = connect_proxy
    network = Network(resolver=_resolver([]), ssl_context=stub_network.ssl_context)
    url = f"http://user:p%40ss@127.0.0.1:{port}"
    async with egress_x2.client(EXTERNAL, timeout=5, network=network, proxy=url) as client:
        response = await client.get(openai_tls_stub.base_url + "/models")
    assert response.status_code == 200
    assert proxy.targets == [f"provider.test:{openai_tls_stub.port}"]
    assert len(proxy.auth) == 1
    assert "authorization" not in {k.lower() for k in openai_tls_stub.state.log[0].headers}


async def test_the_proxy_still_refuses_address_literals_it_may_not_reach(
    connect_proxy: tuple[_ConnectProxy, int],
) -> None:
    proxy, port = connect_proxy
    async with egress_x2.client(EXTERNAL, timeout=5, proxy=f"http://127.0.0.1:{port}") as client:
        with pytest.raises(EgressBlocked):
            await client.get("https://10.0.0.1/v1/models")
    assert proxy.targets == []


async def test_local_connections_do_not_use_the_proxy(
    openai_stub: OpenAIStub, connect_proxy: tuple[_ConnectProxy, int]
) -> None:
    proxy, port = connect_proxy
    async with egress_x2.client(LOCAL, timeout=5, proxy=f"http://127.0.0.1:{port}") as client:
        assert (await client.get(openai_stub.base_url + "/models")).status_code == 200
    assert proxy.targets == []


def test_a_proxy_url_keeps_its_credentials_apart() -> None:
    target = ProxyTarget.parse("http://user:p%40ss@proxy.internal:3128")
    assert target == ProxyTarget("http://proxy.internal:3128", ("user", "p@ss"))
    with pytest.raises(ValueError):
        ProxyTarget.parse("socks5://proxy.internal:1080")


async def test_the_connection_checks_use_the_proxy_too(
    openai_tls_stub: OpenAIStub,
    stub_network: Network,
    connect_proxy: tuple[_ConnectProxy, int],
) -> None:
    """`egress.client` (httpx: connection test and model listing) follows the same rule."""
    proxy, port = connect_proxy
    network = Network(resolver=_resolver([]), ssl_context=stub_network.ssl_context)
    async with egress.client(
        EXTERNAL, timeout=5, network=network, proxy=f"http://127.0.0.1:{port}"
    ) as client:
        assert (await client.get(openai_tls_stub.base_url + "/models")).status_code == 200
        with pytest.raises(EgressBlocked):
            await client.get("https://[::ffff:10.0.0.1]/v1/models")
    assert proxy.targets == [f"provider.test:{openai_tls_stub.port}"]
