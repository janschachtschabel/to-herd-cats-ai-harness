"""The role `worker`: the dispatcher and the internal port, nothing else; `all` runs it
too. SIGTERM lets the batch in progress finish."""

import asyncio
import signal
import socket
from collections import Counter

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app import launch
from app.core.config import Settings
from app.core.outbox import Event
from app.web.internal import create_internal_app, get_engine
from app.worker.dispatcher import Dispatcher
from app.worker.main import Worker
from app.worker.registry import HandlerRegistry
from tests.outbox_helpers import emit_committed, outbox_row
from tests.real_db import RealDb


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _wait_until(check, seconds: float = 15.0) -> None:  # noqa: ASYNC109
    async with asyncio.timeout(seconds):
        while not await check():  # noqa: ASYNC110 -- polls another process's state
            await asyncio.sleep(0.05)


def test_worker_and_all_roles_serve() -> None:
    assert launch.steps_for("worker") == ("serve",)
    assert launch.steps_for("all") == ("migrate", "serve")


async def test_worker_role_runs_the_internal_port_and_the_worker_only(monkeypatch) -> None:
    seen: list[object] = []

    async def fake_bootstrap(settings: Settings) -> None:
        seen.append("bootstrap")

    async def fake_run_servers(servers) -> int:  # type: ignore[no-untyped-def]
        seen.append([type(s).__name__ for s in servers])
        seen.append([getattr(s, "config", None) and s.config.port for s in servers])
        return 0

    monkeypatch.setattr(launch, "bootstrap", fake_bootstrap)
    monkeypatch.setattr(launch, "run_servers", fake_run_servers)
    assert await launch.serve(Settings(role="worker", internal_port=9191)) == 0
    assert seen == [["_Server", "Worker"], [9191, None]]


async def test_all_runs_the_worker_too(monkeypatch) -> None:
    seen: list[list[str]] = []

    async def fake_bootstrap(settings: Settings) -> None:
        pass

    async def fake_run_servers(servers) -> int:  # type: ignore[no-untyped-def]
        seen.append([type(s).__name__ for s in servers])
        return 0

    monkeypatch.setattr(launch, "bootstrap", fake_bootstrap)
    monkeypatch.setattr(launch, "run_servers", fake_run_servers)
    assert await launch.serve(Settings(role="all", internal_token=None)) == 0
    assert await launch.serve(Settings(role="api")) == 0
    assert seen == [["_Server", "_Server", "Worker"], ["_Server", "_Server"]]


async def test_ready_waits_for_the_worker(engine) -> None:
    class FakeWorker:
        ready = False

    worker = FakeWorker()
    app = create_internal_app(worker=worker)
    app.dependency_overrides[get_engine] = lambda: engine
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://i") as client:
        response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "reason": "worker"}
        worker.ready = True
        assert (await client.get("/ready")).status_code == 200


async def test_worker_finishes_its_batch_on_stop(real_db: RealDb) -> None:
    registry = HandlerRegistry()
    started = asyncio.Event()
    finished: Counter[str] = Counter()

    @registry.handler("test", "slow")
    async def _slow(session, event: Event) -> None:
        started.set()
        await asyncio.sleep(0.5)
        finished[str(event.id)] += 1

    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    worker = Worker(Dispatcher(real_db.database, registry))
    task = asyncio.create_task(worker.serve())
    await asyncio.wait_for(started.wait(), timeout=10)
    worker.should_exit = True
    await asyncio.wait_for(task, timeout=10)
    assert finished == Counter({str(event_id): 1})
    assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None
    assert worker.ready is False


async def test_worker_role_starts_and_stops_on_sigterm(real_db: RealDb) -> None:
    internal, public = _free_port(), _free_port()
    settings = Settings(role="worker", internal_port=internal, public_port=public)
    serving = asyncio.create_task(launch.serve(settings))
    async with httpx.AsyncClient(timeout=2) as client:

        async def ready() -> bool:
            try:
                response = await client.get(f"http://127.0.0.1:{internal}/ready")
            except httpx.TransportError:
                return False
            return response.status_code == 200

        try:
            await _wait_until(ready)
            with pytest.raises(httpx.ConnectError):
                await client.get(f"http://127.0.0.1:{public}/api/auth/me")

            (event_id,) = await emit_committed(real_db.database, real_db.org_id)

            async def dispatched() -> bool:
                return (await outbox_row(real_db.database, event_id)).dispatched_at is not None

            await _wait_until(dispatched, seconds=1.5)  # woken by NOTIFY, not the 2 s poll
        finally:
            signal.raise_signal(signal.SIGTERM)
            assert await asyncio.wait_for(serving, timeout=15) == 0
