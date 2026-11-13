"""The guard on outbound calls (plan M5 decision 7, review focus 5): only https (http
for `local`), the name resolved when connecting and the connection made to exactly the
address checked, no redirects followed, private addresses only for `local`, link-local
and metadata addresses never."""

import ipaddress
from collections.abc import Sequence

import httpcore
import httpx
import pytest

from app.core import egress
from app.core.egress import EgressBlocked, EgressRules, Network
from tests.support.openai_stub import OpenAIStub

EXTERNAL = EgressRules(allow_private=False, allow_http=False)
LOCAL = EgressRules(allow_private=True, allow_http=True)

ALWAYS_BLOCKED = [
    "169.254.169.254",  # cloud metadata
    "169.254.1.1",
    "fe80::1",
    "0.0.0.0",
    "::",
    "224.0.0.1",
    "ff02::1",
    "255.255.255.255",
    "240.0.0.1",
    "fd00:ec2::254",  # AWS metadata over IPv6
    "100.100.100.200",  # Alibaba metadata
    "168.63.129.16",  # Azure host endpoint
    "::ffff:169.254.169.254",  # IPv4-mapped
    "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
    "2002:a9fe:a9fe::",  # 6to4 of 169.254.169.254
    "::169.254.169.254",  # IPv4-compatible
]
PRIVATE = [
    "10.0.0.1",
    "172.16.5.4",
    "192.168.1.1",
    "127.0.0.1",
    "127.1.2.3",
    "::1",
    "fd12:3456::1",
    "100.64.0.1",  # carrier-grade NAT
    "::ffff:127.0.0.1",
    "::ffff:10.0.0.1",
    "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
    "2002:7f00:1::",  # 6to4 of 127.0.0.1
    "::127.0.0.1",
    "192.0.2.10",  # documentation range: not global
]
PUBLIC = ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"]


@pytest.mark.parametrize("address", ALWAYS_BLOCKED)
def test_link_local_and_metadata_addresses_are_never_allowed(address: str) -> None:
    for rules in (EXTERNAL, LOCAL):
        with pytest.raises(EgressBlocked):
            egress.check_address(ipaddress.ip_address(address), rules)


@pytest.mark.parametrize("address", PRIVATE)
def test_private_addresses_only_for_local_connections(address: str) -> None:
    with pytest.raises(EgressBlocked):
        egress.check_address(ipaddress.ip_address(address), EXTERNAL)
    egress.check_address(ipaddress.ip_address(address), LOCAL)


@pytest.mark.parametrize("address", PUBLIC)
def test_public_addresses_are_allowed(address: str) -> None:
    egress.check_address(ipaddress.ip_address(address), EXTERNAL)


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/v1",  # http only for local
        "ftp://api.example.com/v1",
        "file:///etc/passwd",
        "https://user:pw@api.example.com/v1",  # credentials in a URL
        "https://api.example.com/v1?api-key=x",  # a query (where keys like to hide)
        "https://api.example.com/v1#x",
        "https:///v1",
        "https://127.0.0.1/v1",
        "https://[::1]/v1",
        "https://[::ffff:127.0.0.1]/v1",
        "https://169.254.169.254/latest",
        "https://2130706433/v1",  # 127.0.0.1 as one number
        "https://0x7f.1/v1",  # and in hex
        "https://0177.0.0.1/v1",  # and in octal
        "https://localhost/v1",
        "https://api.localhost/v1",
        "https://api.example.com:99999/v1",
        "not a url",
    ],
)
def test_base_urls_that_external_connections_may_not_use(url: str) -> None:
    with pytest.raises(EgressBlocked):
        egress.check_base_url(url, EXTERNAL)


def test_local_connections_may_use_http_and_private_addresses() -> None:
    assert egress.check_base_url("http://127.0.0.1:11434/v1/", LOCAL) == "http://127.0.0.1:11434/v1"
    assert egress.check_base_url("http://ollama.internal/v1", LOCAL) == "http://ollama.internal/v1"
    with pytest.raises(EgressBlocked):
        egress.check_base_url("http://169.254.169.254/v1", LOCAL)
    with pytest.raises(EgressBlocked):
        egress.check_base_url("gopher://127.0.0.1/v1", LOCAL)


def test_a_normal_base_url_is_kept() -> None:
    url = "https://api.openai.com/v1"
    assert egress.check_base_url(url + "/", EXTERNAL) == url


class _Recorder(httpcore.AsyncNetworkBackend):
    """Stands in for the real network: records where it was asked to connect."""

    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):  # type: ignore[no-untyped-def]  # noqa: ASYNC109
        self.hosts.append(host)
        raise httpcore.ConnectError("recorded")


def _resolver(*answers: Sequence[str]):  # type: ignore[no-untyped-def]
    calls: list[str] = []
    queue = list(answers)

    async def resolve(host: str, port: int) -> list[str]:
        calls.append(host)
        return list(queue.pop(0) if len(queue) > 1 else queue[0])

    resolve.calls = calls  # type: ignore[attr-defined]
    return resolve


async def test_the_name_is_resolved_on_connect_and_only_checked_addresses_are_dialled() -> None:
    """DNS may change between a check and the call (rebinding): there is no separate
    check, the connection goes to exactly the address that was checked."""
    recorder = _Recorder()
    resolve = _resolver(["93.184.216.34"], ["127.0.0.1"])
    backend = egress.GuardedBackend(EXTERNAL, Network(resolver=resolve), inner=recorder)
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("api.example.com", 443)
    assert recorder.hosts == ["93.184.216.34"]
    with pytest.raises(EgressBlocked):
        await backend.connect_tcp("api.example.com", 443)  # now it answers 127.0.0.1
    assert recorder.hosts == ["93.184.216.34"]
    assert resolve.calls == ["api.example.com", "api.example.com"]  # type: ignore[attr-defined]


async def test_one_forbidden_address_among_the_answers_blocks_the_name() -> None:
    recorder = _Recorder()
    resolve = _resolver(["93.184.216.34", "10.0.0.7"])
    backend = egress.GuardedBackend(EXTERNAL, Network(resolver=resolve), inner=recorder)
    with pytest.raises(EgressBlocked):
        await backend.connect_tcp("api.example.com", 443)
    assert recorder.hosts == []


async def test_unresolvable_names_and_odd_answers_are_blocked() -> None:
    for answer in ([], ["fe80::1%eth0"], ["not-an-ip"]):
        backend = egress.GuardedBackend(EXTERNAL, Network(resolver=_resolver(answer)))
        with pytest.raises(EgressBlocked):
            await backend.connect_tcp("api.example.com", 443)


async def test_a_client_never_reaches_loopback_for_an_external_connection(
    openai_stub: OpenAIStub,
) -> None:
    async with egress.client(EXTERNAL, timeout=5) as client:
        with pytest.raises(EgressBlocked):
            await client.get(openai_stub.base_url.replace("http:", "https:") + "/models")
        with pytest.raises(EgressBlocked):  # http itself is not allowed either
            await client.get(openai_stub.base_url + "/models")
    assert openai_stub.state.log == []


async def test_a_local_client_reaches_loopback_and_ignores_proxy_settings(
    openai_stub: OpenAIStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.invalid:3128")
    async with egress.client(LOCAL, timeout=5) as client:
        response = await client.get(openai_stub.base_url + "/models")
    assert response.status_code == 200
    assert len(openai_stub.state.log) == 1


async def test_redirects_are_not_followed(openai_stub: OpenAIStub) -> None:
    openai_stub.state.redirect_to = "http://169.254.169.254/latest/meta-data"
    async with egress.client(LOCAL, timeout=5) as client:
        response = await client.get(openai_stub.base_url + "/models")
    assert response.status_code == 302
    assert len(openai_stub.state.log) == 1


async def test_tls_to_a_pinned_address_still_verifies_the_name(
    openai_tls_stub: OpenAIStub, stub_network: Network
) -> None:
    """The connection goes to the checked address, the certificate is checked against
    the name in the URL (SNI)."""
    async with egress.client(EXTERNAL, timeout=5, network=stub_network) as client:
        response = await client.get(openai_tls_stub.base_url + "/models")
    assert response.status_code == 200
    wrong_name = openai_tls_stub.base_url.replace("provider.test", "other.test")
    network = Network(
        resolver=stub_network.resolver,
        ssl_context=stub_network.ssl_context,
        extra_allowed=stub_network.extra_allowed,
    )
    async with egress.client(EXTERNAL, timeout=5, network=network) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get(wrong_name + "/models")
