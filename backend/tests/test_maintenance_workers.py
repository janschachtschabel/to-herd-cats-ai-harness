"""The worker's loops pause in maintenance (plan M9 decision 9): the outbox routes and
delivers nothing (and removes nothing), the run loop claims and sweeps nothing and
cancels the runs it holds (their leases run out; after maintenance a worker takes
them up again from their journal), the due loop fires, reviews and cleans nothing.
Once maintenance ends, everything goes on where it was."""

import asyncio
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.maintenance.cache import INACTIVE, MaintenanceCache, maintenance_cache
from app.modules.maintenance.models import MaintenanceReason
from app.modules.maintenance.state import MaintenanceState
from app.worker.dispatcher import Dispatcher
from app.worker.due import DueLoop
from app.worker.runs import RunLoop
from tests.outbox_helpers import Calls, effects, emit_committed, registry_of
from tests.real_db import RealDb
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)
ON = MaintenanceState(active=True, reason=MaintenanceReason.RESTORE, started_at=AT)


@pytest.fixture
def maintenance() -> Iterator[MaintenanceCache]:
    cache = maintenance_cache()
    try:
        yield cache
    finally:
        cache.state = INACTIVE


async def test_workers_pause_in_maintenance(
    real_db: RealDb, maintenance: MaintenanceCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = real_db.database
    calls: Calls = Counter()
    dispatcher = Dispatcher(database, registry_of(calls, ["a"]))
    [event_id] = await emit_committed(database, real_db.org_id)
    ran: list[str] = []
    for name, owner in (
        ("claim", RunLoop),
        ("sweep_once", RunLoop),
        ("pass_once", DueLoop),
        ("review_once", DueLoop),
        ("cleanup_if_due", DueLoop),
    ):
        monkeypatch.setattr(owner, name, lambda self, *a, _n=name: _record(ran, _n))
    runs = RunLoop(database, concurrency=2, lease=30)
    due = DueLoop(database, clock=SettableClock(AT))
    held = asyncio.create_task(asyncio.Event().wait())  # a run in progress
    runs.held[real_db.org_id] = (1, held)  # type: ignore[index]

    maintenance.state = ON
    assert await dispatcher.dispatch_batch() == 0
    await dispatcher.cleanup_if_due()
    assert await effects(database, event_id) == Counter()
    await runs.one_round(asyncio.Event())
    assert await due.round() is False
    assert ran == []
    with pytest.raises(asyncio.CancelledError):
        await held
    assert runs.held == {}

    maintenance.state = INACTIVE
    await dispatcher.drain()
    assert await effects(database, event_id) == Counter({"a": 1})
    await runs.one_round(asyncio.Event())
    await due.round()
    assert ran == ["sweep_once", "claim", "pass_once", "review_once", "cleanup_if_due"]


async def _record(ran: list[str], name: str) -> Any:
    ran.append(name)
    return None if name == "claim" else 0
