"""A handler's after-commit actions (`core.db.after_commit`) in a lane: they run once
the lane's batch has committed, exactly once per event that kept its effect; an
event whose call failed (and whose savepoint was rolled back) leaves none behind,
also when its neighbours had to run a second time one by one. Real commits."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import after_commit
from app.core.outbox import Event
from app.worker.dispatcher import Dispatcher
from app.worker.registry import HandlerRegistry
from tests.outbox_helpers import delivered, emit_committed
from tests.real_db import RealDb


async def test_actions_run_after_the_commit_once_per_kept_event(real_db: RealDb) -> None:
    ids = await emit_committed(real_db.database, real_db.org_id, 5)
    poisoned = ids[2]
    ran: list[uuid.UUID] = []
    committed: list[bool] = []
    registry = HandlerRegistry()

    @registry.handler("test.happened", "counts")
    async def _counts(session: AsyncSession, event: Event) -> None:
        async def action(_: AsyncSession) -> None:
            ran.append(event.id)
            # seen from another connection: the delivery is committed already
            committed.append(await delivered(real_db.database, event.id) == {"counts"})

        after_commit(session, action)
        if event.id == poisoned:
            raise RuntimeError("handler failed")

    await Dispatcher(real_db.database, registry).dispatch_batch()
    assert sorted(ran) == sorted(i for i in ids if i != poisoned)  # once each, in spite of
    assert all(committed)  # the first pass that was rolled back at the poisoned event


async def test_a_batch_that_fails_as_a_whole_runs_no_action(real_db: RealDb) -> None:
    [event_id] = await emit_committed(real_db.database, real_db.org_id, 1)
    ran: list[uuid.UUID] = []
    registry = HandlerRegistry()

    @registry.handler("test.happened", "fails")
    async def _fails(session: AsyncSession, event: Event) -> None:
        async def action(_: AsyncSession) -> None:
            ran.append(event.id)

        after_commit(session, action)
        raise RuntimeError("handler failed")

    await Dispatcher(real_db.database, registry).dispatch_batch()
    assert ran == []
    assert await delivered(real_db.database, event_id) == set()
