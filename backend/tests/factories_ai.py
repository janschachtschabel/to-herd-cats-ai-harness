"""AI test fixtures: the OpenAI-protocol stub (plain and with TLS) and the network that
lets the egress guard reach it.

- `openai_stub`: http on 127.0.0.1, for connections of kind `local`.
- `openai_tls_stub`: https for the name `provider.test`, for kinds that need https.
- `stub_network`: resolves `*.test` to 127.0.0.1, trusts the stub's certificate and
  allows 127.0.0.1 in addition; `stub_egress` installs it for code that builds its own
  clients (the services). Production rules stay as they are.
"""

import ipaddress
import ssl
from collections.abc import Iterator

import pytest

from app.core import egress
from app.core.egress import Network
from tests.support.openai_stub import OpenAIStub

TLS_NAME = "provider.test"


@pytest.fixture(scope="session")
def _plain_stub() -> Iterator[OpenAIStub]:
    stub = OpenAIStub().start()
    yield stub
    stub.stop()


@pytest.fixture(scope="session")
def _tls_stub() -> Iterator[OpenAIStub]:
    stub = OpenAIStub(tls_name=TLS_NAME).start()
    yield stub
    stub.stop()


@pytest.fixture
def openai_stub(_plain_stub: OpenAIStub) -> Iterator[OpenAIStub]:
    _plain_stub.state.reset()
    yield _plain_stub
    _plain_stub.state.reset()


@pytest.fixture
def openai_tls_stub(_tls_stub: OpenAIStub) -> Iterator[OpenAIStub]:
    _tls_stub.state.reset()
    yield _tls_stub
    _tls_stub.state.reset()


async def _resolve_test_names(host: str, port: int) -> list[str]:
    if host.endswith(".test"):
        return ["127.0.0.1"]
    raise OSError("unknown name")


@pytest.fixture
def stub_network(openai_tls_stub: OpenAIStub) -> Network:
    context = ssl.create_default_context(cafile=str(openai_tls_stub.cert_path))
    return Network(
        resolver=_resolve_test_names,
        ssl_context=context,
        extra_allowed=(ipaddress.ip_network("127.0.0.1/32"),),
    )


@pytest.fixture
def stub_egress(stub_network: Network, monkeypatch: pytest.MonkeyPatch) -> Network:
    monkeypatch.setattr(egress, "_network", stub_network)
    return stub_network
