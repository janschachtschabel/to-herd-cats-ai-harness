import asyncio
import signal
import sys

import pytest

from app import launch
from app.core.config import Settings


@pytest.mark.parametrize(
    ("role", "steps"),
    [
        ("api", ("serve",)),
        ("migrate", ("migrate",)),
        ("all", ("migrate", "serve")),
        ("collab", ("collab",)),
    ],
)
def test_steps_per_role(role, steps):
    assert launch.steps_for(role) == steps


@pytest.mark.parametrize(
    ("role", "calls"),
    [("api", ["serve"]), ("migrate", ["migrate"]), ("all", ["migrate", "serve"])],
)
def test_main_runs_the_steps_in_order(monkeypatch, role, calls):
    seen: list[str] = []
    monkeypatch.setattr(launch, "get_settings", lambda: Settings(role=role))
    monkeypatch.setattr(launch, "upgrade_head", lambda: seen.append("migrate"))

    async def fake_serve(settings):
        seen.append("serve")
        return 0

    monkeypatch.setattr(launch, "serve", fake_serve)
    launch.main()
    assert seen == calls


def test_uvicorn_configs_disable_access_log_and_keep_our_logging():
    public, internal = launch.server_configs(Settings(public_port=8080, internal_port=9090))
    assert (public.port, internal.port) == (8080, 9090)
    for config in (public, internal):
        assert config.access_log is False and config.log_config is None


def test_websocket_messages_are_limited_to_1_mib():
    public, _ = launch.server_configs(Settings())
    assert public.ws_max_size == 1024 * 1024


def test_public_server_trusts_forwarded_headers_only_from_configured_proxies():
    settings = Settings(forwarded_allow_ips="10.0.0.0/8,127.0.0.1")
    public, internal = launch.server_configs(settings)
    assert public.proxy_headers is True
    assert public.forwarded_allow_ips == "10.0.0.0/8,127.0.0.1"
    # The internal port is reached directly (probes, scrapes): no forwarded headers.
    assert internal.proxy_headers is False


def test_forwarded_allow_ips_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("HERD_FORWARDED_ALLOW_IPS", raising=False)
    assert Settings().forwarded_allow_ips == "127.0.0.1"
    monkeypatch.setenv("HERD_FORWARDED_ALLOW_IPS", "172.16.0.0/12")
    assert Settings().forwarded_allow_ips == "172.16.0.0/12"


class FakeServer:
    def __init__(self) -> None:
        self.should_exit = False
        self.stopped = False

    async def serve(self) -> None:
        while not self.should_exit:  # noqa: ASYNC110 -- uvicorn.Server polls should_exit too
            await asyncio.sleep(0.01)
        self.stopped = True


async def test_sigterm_stops_both_servers():
    servers = [FakeServer(), FakeServer()]
    loop = asyncio.get_running_loop()
    loop.call_later(0.05, signal.raise_signal, signal.SIGTERM)
    assert await asyncio.wait_for(launch.run_servers(servers), timeout=5) == 0
    assert all(s.stopped for s in servers)


async def test_one_server_ending_stops_the_other():
    class Crashing(FakeServer):
        async def serve(self) -> None:
            raise SystemExit(1)  # what uvicorn does when it cannot bind

    other = FakeServer()
    assert await asyncio.wait_for(launch.run_servers([Crashing(), other]), timeout=5) == 1
    assert other.stopped


def test_main_exits_with_the_servers_exit_code(monkeypatch):
    monkeypatch.setattr(launch, "get_settings", lambda: Settings(role="api"))

    async def failing_serve(settings):
        return 1

    monkeypatch.setattr(launch, "serve", failing_serve)
    with pytest.raises(SystemExit) as exited:
        launch.main()
    assert exited.value.code == 1


async def test_serve_bootstraps_before_serving(monkeypatch):
    seen: list[str] = []

    async def fake_bootstrap(settings):
        seen.append("bootstrap")

    async def fake_run_servers(servers):
        seen.append(f"run {len(servers)}")
        return 0

    monkeypatch.setattr(launch, "bootstrap", fake_bootstrap)
    monkeypatch.setattr(launch, "run_servers", fake_run_servers)
    assert await launch.serve(Settings(role="api")) == 0
    assert seen == ["bootstrap", "run 2"]


async def test_bootstrap_runs_in_its_own_committed_transaction(monkeypatch):
    seen: list[object] = []

    class FakeSession:
        async def commit(self) -> None:
            seen.append("commit")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: object) -> None:
            seen.append("closed")

    class FakeDatabase:
        session_factory = FakeSession

    async def fake_ensure(session, settings):
        seen.append(("ensure", type(session).__name__, settings.bootstrap_org_name))

    monkeypatch.setattr(launch, "get_database", lambda: FakeDatabase())
    monkeypatch.setattr(launch, "ensure_bootstrap", fake_ensure)
    await launch.bootstrap(Settings(bootstrap_org_name="Acme"))
    assert seen == [("ensure", "FakeSession", "Acme"), "commit", "closed"]


TOKEN = "l" * 40


async def test_all_starts_the_collab_process_only_with_an_internal_token(monkeypatch):
    seen: list[object] = []

    async def fake_bootstrap(settings):
        pass

    async def fake_run_servers(servers):
        seen.append(servers)
        return 0

    monkeypatch.setattr(launch, "bootstrap", fake_bootstrap)
    monkeypatch.setattr(launch, "run_servers", fake_run_servers)
    await launch.serve(Settings(role="all"))
    await launch.serve(Settings(role="all", internal_token=TOKEN, internal_port=9191))
    await launch.serve(Settings(role="api", internal_token=TOKEN))
    without, with_token, api = seen
    assert len(without) == 2 and len(api) == 2
    assert len(with_token) == 3
    child = with_token[2]
    assert isinstance(child, launch.CollabProcess)
    assert child.command[0] == "node" and child.command[1].endswith("collab/server.mjs")
    assert child.env["HERD_COLLAB_HOST"] == "127.0.0.1"
    assert child.env["HERD_COLLAB_API_URL"] == "http://127.0.0.1:9191"
    assert child.env["HERD_INTERNAL_TOKEN"] == TOKEN
    assert child.env["HERD_COLLAB_PORT"] == "1234"


async def test_collab_process_is_stopped_with_the_servers():
    child = launch.CollabProcess([sys.executable, "-c", "import time; time.sleep(30)"], {})
    loop = asyncio.get_running_loop()
    loop.call_later(0.3, signal.raise_signal, signal.SIGTERM)
    other = FakeServer()
    assert await asyncio.wait_for(launch.run_servers([other, child]), timeout=10) == 0
    assert other.stopped
    assert child.returncode is not None


async def test_collab_process_ending_ends_the_launcher_with_3():
    child = launch.CollabProcess([sys.executable, "-c", "pass"], {})
    other = FakeServer()
    assert await asyncio.wait_for(launch.run_servers([other, child]), timeout=10) == 3
    assert other.stopped


async def test_missing_node_ends_the_launcher_with_3():
    child = launch.CollabProcess(["/nonexistent/node"], {})
    assert await asyncio.wait_for(launch.run_servers([FakeServer(), child]), timeout=10) == 3


def test_role_collab_runs_node_in_place(monkeypatch):
    calls = []
    settings = Settings(role="collab", internal_token=TOKEN, collab_api_url="http://api:9090")
    monkeypatch.setattr(launch, "get_settings", lambda: settings)
    monkeypatch.setattr(launch.os, "execvpe", lambda *args: calls.append(args))
    launch.main()
    ((file, argv, env),) = calls
    assert file == "node" and argv[1].endswith("collab/server.mjs")
    assert env["HERD_COLLAB_HOST"] == "0.0.0.0"
    assert env["HERD_COLLAB_API_URL"] == "http://api:9090"
