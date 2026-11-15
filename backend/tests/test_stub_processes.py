"""The MCP and OAuth stubs as processes (the browser tests and the M8 demo start them
so): with `--certfile`/`--keyfile` they serve https for the name `--name`, so the app,
which dials MCP servers and OAuth endpoints over https only, reaches them on the local
machine (the name listed in HERD_MCP_ALLOWED_HOSTS, the certificate trusted through
SSL_CERT_FILE). The OAuth stub's metadata then names its https base."""

import os
import ssl
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from tests.live_helpers import free_port
from tests.support.openai_stub import self_signed

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def certificate(tmp_path: Path) -> tuple[Path, Path]:
    return self_signed(tmp_path, ["localhost"])


def _start(module: str, port: int, cert: Path, key: Path) -> subprocess.Popen[bytes]:
    args = [sys.executable, "-m", module, "--port", str(port)]
    args += ["--certfile", str(cert), "--keyfile", str(key), "--name", "localhost"]
    return subprocess.Popen(args, cwd=BACKEND, env=os.environ.copy())


def _get(process: subprocess.Popen[bytes], url: str, cert: Path) -> httpx.Response:
    trusted = ssl.create_default_context(cafile=str(cert))
    deadline = time.monotonic() + 30
    while True:
        assert process.poll() is None, "the stub ended"
        try:
            return httpx.get(url, verify=trusted)
        except httpx.ConnectError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


@pytest.fixture
def stopped() -> Iterator[list[subprocess.Popen[bytes]]]:
    processes: list[subprocess.Popen[bytes]] = []
    yield processes
    for process in processes:
        process.terminate()
        process.wait(timeout=10)


def test_the_mcp_stub_serves_https_for_its_name(
    certificate: tuple[Path, Path], stopped: list[subprocess.Popen[bytes]]
) -> None:
    cert, key = certificate
    port = free_port()
    stopped.append(stub := _start("tests.support.mcp_stub", port, cert, key))
    response = _get(stub, f"https://localhost:{port}/_stub/log", cert)
    assert response.status_code == 200
    assert response.json() == []


def test_the_oauth_stub_serves_https_and_names_its_https_base(
    certificate: tuple[Path, Path], stopped: list[subprocess.Popen[bytes]]
) -> None:
    cert, key = certificate
    port = free_port()
    stopped.append(stub := _start("tests.support.oauth_stub", port, cert, key))
    response = _get(stub, f"https://localhost:{port}/.well-known/oauth-authorization-server", cert)
    assert response.status_code == 200
    base = f"https://localhost:{port}"
    assert response.json()["issuer"] == base
    assert response.json()["token_endpoint"] == f"{base}/token"


def test_a_scripted_tool_answers_late_and_the_list_does_not(
    certificate: tuple[Path, Path], stopped: list[subprocess.Popen[bytes]]
) -> None:
    """`results: {tool: {"delay": s}}` holds only that tool's call (a worker lost while
    an external call is in flight, in e2e); the tool list in the same exchange answers
    at once."""
    cert, key = certificate
    port = free_port()
    stopped.append(stub := _start("tests.support.mcp_stub", port, cert, key))
    base = f"https://localhost:{port}"
    _get(stub, f"{base}/_stub/log", cert)
    trusted = ssl.create_default_context(cafile=str(cert))
    script = {"results": {"search_issues": {"text": "late", "delay": 1.5}}}
    assert httpx.post(f"{base}/_stub/script", json=script, verify=trusted).status_code == 200
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    }

    def rpc(method: str, params: dict[str, object] | None = None) -> tuple[float, object]:
        body: dict[str, object] = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            body["params"] = params
        started = time.monotonic()
        response = httpx.post(f"{base}/mcp", json=body, headers=headers, verify=trusted)
        assert response.status_code == 200, response.text
        return time.monotonic() - started, response.json()["result"]

    listed_in, _ = rpc("tools/list")
    called_in, result = rpc("tools/call", {"name": "search_issues", "arguments": {"q": "x"}})
    assert listed_in < 1.0
    assert called_in >= 1.5
    assert result["content"][0]["text"] == "late"  # type: ignore[index]
