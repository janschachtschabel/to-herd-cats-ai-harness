"""A worker that hangs or is missing must show (review M3 N3, N4): every handler call
has a time limit (asyncio and the database's lock/statement timeouts) that counts as a
failed attempt, the backlog gauges are read on a timer of their own, `/ready` turns
not ready without progress, and only processes that run a worker export the outbox
gauges, the failed count read from the database included."""

import asyncio
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import func, text, update

from app.core.listen import asyncpg_dsn
from app.core.metrics import REGISTRY
from app.core.outbox import Event, EventOutbox
from app.worker import main as worker_main
from app.worker.dispatcher import Dispatcher, Routed
from app.worker.main import Worker
from app.worker.registry import HandlerRegistry
from tests.conftest import json_lines
from tests.outbox_helpers import delivered, emit_committed, lane_row, outbox_row
from tests.real_db import RealDb

BACKEND = Path(__file__).resolve().parent.parent


def _sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_a_hanging_handler_times_out_and_does_not_hold_up_the_others(
    real_db: RealDb, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = HandlerRegistry()
    calls: Counter[str] = Counter()

    @registry.handler("test", "hangs")
    async def _hangs(session, event: Event) -> None:
        calls["hangs"] += 1
        await asyncio.sleep(3600)

    @registry.handler("test", "fine")
    async def _fine(session, event: Event) -> None:
        calls["fine"] += 1

    first, second, third = await emit_committed(real_db.database, real_db.org_id, 3)
    timeouts = _sample("herd_outbox_dispatch_total", handler="hangs", result="timeout")
    dispatcher = Dispatcher(real_db.database, registry, handler_timeout=0.3)
    started = time.monotonic()
    assert await dispatcher.dispatch_batch() == 3 + 3 + 3  # routed, each lane's batch
    assert time.monotonic() - started < 2.0  # one limit, not one per event
    assert calls == Counter({"hangs": 1, "fine": 3})  # tried once in this batch
    lane = await lane_row(real_db.database, first, "hangs")
    assert lane is not None and lane.attempts == 1 and lane.failed_at is None
    assert (await outbox_row(real_db.database, first)).dispatched_at is None
    for later in (second, third):  # not tried yet: due again, no attempt counted
        lane = await lane_row(real_db.database, later, "hangs")
        assert lane is not None and lane.attempts == 0
        assert (await outbox_row(real_db.database, later)).dispatched_at is None
        assert await delivered(real_db.database, later) == {"fine"}
    assert _sample("herd_outbox_dispatch_total", handler="hangs", result="timeout") == (
        timeouts + 1
    )
    lines = [line for line in json_lines(capsys.readouterr().out) if "outbox" in line["message"]]
    assert [line["message"] for line in lines] == ["outbox.handler_timeout"]
    assert lines[0]["handler"] == "hangs" and lines[0]["event_id"] == str(first)


async def test_a_lock_wait_in_the_database_is_ended_by_the_limit(real_db: RealDb) -> None:
    registry = HandlerRegistry()
    settings: list[tuple[str, str]] = []

    @registry.handler("test", "locked")
    async def _locked(session, event: Event) -> None:
        settings.append(
            (
                await session.scalar(text("SHOW lock_timeout")),
                await session.scalar(text("SHOW statement_timeout")),
            )
        )
        await session.execute(text("SELECT 1 FROM notification LIMIT 1"))

    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    holder = await asyncpg.connect(asyncpg_dsn(real_db.database.engine.url))
    holding = holder.transaction()
    await holding.start()
    await holder.execute("LOCK TABLE notification IN ACCESS EXCLUSIVE MODE")
    try:
        timeouts = _sample("herd_outbox_dispatch_total", handler="locked", result="timeout")
        dispatcher = Dispatcher(real_db.database, registry, handler_timeout=0.5)
        started = time.monotonic()
        await dispatcher.dispatch_batch()
        assert time.monotonic() - started < 3.0
    finally:
        await holding.rollback()
        await holder.close()
    assert settings == [("500ms", "500ms")]  # the database's own limits, per transaction
    assert _sample("herd_outbox_dispatch_total", handler="locked", result="timeout") == (
        timeouts + 1
    )
    lane = await lane_row(real_db.database, event_id, "locked")
    assert lane is not None and lane.attempts == 1


async def test_the_gauges_stay_current_while_a_pass_hangs(
    real_db: RealDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker_main, "METRICS_SECONDS", 0.1)
    registry = HandlerRegistry()
    started, release = asyncio.Event(), asyncio.Event()

    @registry.handler("test", "stuck")
    async def _stuck(session, event: Event) -> None:
        started.set()
        await release.wait()

    await emit_committed(real_db.database, real_db.org_id, 2)
    worker = Worker(Dispatcher(real_db.database, registry, handler_timeout=30))
    task = asyncio.create_task(worker.serve())
    try:
        await asyncio.wait_for(started.wait(), timeout=10)
        async with asyncio.timeout(5):
            while _sample("herd_outbox_pending") != 2:  # noqa: ASYNC110 -- the metrics task
                await asyncio.sleep(0.05)
    finally:
        release.set()
        worker.should_exit = True
        await asyncio.wait_for(task, timeout=10)


async def test_a_worker_without_progress_is_not_ready(
    real_db: RealDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    dispatcher = Dispatcher(real_db.database, HandlerRegistry(), handler_timeout=0.1)
    worker = Worker(dispatcher)
    assert worker.stall_seconds == pytest.approx(0.4)
    task = asyncio.create_task(worker.serve())
    try:
        async with asyncio.timeout(5):
            while not worker.ready:  # noqa: ASYNC110 -- the first pass
                await asyncio.sleep(0.02)
        last = _sample("herd_worker_last_pass_timestamp_seconds")
        assert abs(last - time.time()) < 5

        hang = asyncio.Event()

        async def _stuck_route() -> Routed:  # a pass that never finishes
            await hang.wait()
            return Routed(0, frozenset())

        monkeypatch.setattr(dispatcher, "route", _stuck_route)
        worker._loops[worker_main.ROUTER].wake.set()
        async with asyncio.timeout(5):
            while worker.ready:  # noqa: ASYNC110 -- turns false after 0.4 s
                await asyncio.sleep(0.02)
        hang.set()
        async with asyncio.timeout(5):
            while not worker.ready:  # noqa: ASYNC110 -- progress again
                await asyncio.sleep(0.02)
    finally:
        worker.should_exit = True
        await asyncio.wait_for(task, timeout=10)
    assert worker.ready is False


async def test_given_up_events_are_counted_from_the_database(real_db: RealDb) -> None:
    ids = await emit_committed(real_db.database, real_db.org_id, 3)
    async with real_db.database.session_factory() as session:
        await session.execute(
            update(EventOutbox).where(EventOutbox.id.in_(ids[:2])).values(failed_at=func.now())
        )
        await session.commit()
    await Dispatcher(real_db.database, HandlerRegistry()).update_metrics()
    assert _sample("herd_outbox_failed") == 2
    assert _sample("herd_outbox_pending") == 1
    await Dispatcher(real_db.database, HandlerRegistry()).update_metrics()  # a new worker
    assert _sample("herd_outbox_failed") == 2


_EXPORTED = """
import sys
from app.core.metrics import render_metrics
import app.launch  # everything an API process imports
from app.web.public import create_public_app
from app.web.internal import create_internal_app
create_public_app(); create_internal_app()
before = render_metrics()[0].decode()
from app.core.db import Database
from app.worker.main import create_worker
create_worker(Database("postgresql+asyncpg://x:y@127.0.0.1:1/none"))
after = render_metrics()[0].decode()
names = ("herd_outbox_pending", "herd_outbox_oldest_pending_seconds", "herd_outbox_failed",
         "herd_worker_last_pass_timestamp_seconds")
print([n for n in names if f"# TYPE {n} gauge" in before])
print([n for n in names if f"# TYPE {n} gauge" in after])
"""


def test_only_processes_with_a_worker_export_the_outbox_gauges() -> None:
    """An API process has no worker: a backlog of 0 from it would hide one that no
    worker works off (HerdWorkerAbsent alerts on the missing worker instead)."""
    out = subprocess.run(
        [sys.executable, "-c", _EXPORTED],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin", "HERD_ENVIRONMENT": "test"},
    ).stdout.splitlines()
    assert out[0] == "[]"
    assert out[1] == (
        "['herd_outbox_pending', 'herd_outbox_oldest_pending_seconds', 'herd_outbox_failed', "
        "'herd_worker_last_pass_timestamp_seconds']"
    )
