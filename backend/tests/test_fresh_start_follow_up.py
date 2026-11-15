"""Module review M8 5, L4 (K4's ruling: every run created before the cut is cancelled,
every run after it starts clean, none ends silently). A DM's run that ends queues a
run for her message sent while it waited (`closing._follow_up`), in its closing
transaction. That transaction holds the DM's row `FOR SHARE`, the lock her own
messages take, so "Neu beginnen" either comes after it and cancels the follow-up with
its notice, or it comes first: then it waits for the ending run's row, which the
closing transaction holds, gives up (409 `conflict.retry`) before Postgres would call
the closing transaction a deadlock's victim, and the follow-up is queued; pressed
again, it cancels the follow-up.

Real commits on two connections, the order fixed by Postgres's lock view, no sleeps
(as `tests/test_fresh_start_races.py`)."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
from app.core.models_base import utcnow
from app.modules.agents.closing import close
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.run_models import Run, RunState, StopReason
from app.modules.messaging.models import Message, MessageKind
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_fresh_start_races import _version, _waits_or_done
from tests.test_run_cancel_races import _ask, _claimed, _dm


async def _set(real_db: RealDb, run_id: uuid.UUID, **values: Any) -> None:
    async with real_db.database.session_factory() as session, session.begin():
        await session.execute(update(Run).where(Run.id == run_id).values(**values))


async def _lease(real_db: RealDb, run_id: uuid.UUID) -> Any:
    async with real_db.database.session_factory() as session:
        return await session.scalar(select(Run.lease_until).where(Run.id == run_id))


async def _second_unanswered(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> tuple[Any, str, uuid.UUID]:
    """Her DM; the first run works, her second message came while it waited for
    something (so it got no run of its own), and the run works again."""
    owner, dm_id, _ = await _dm(real_db, make_real_client, openai_stub)
    first = await _ask(owner, dm_id)
    claimed = await _claimed(real_db)
    assert claimed.id == first
    until = utcnow() + timedelta(hours=1)
    lease = await _lease(real_db, first)
    await _set(real_db, first, state=RunState.WAITING, wait_until=until, lease_until=None)
    r = await owner.post(f"/api/conversations/{dm_id}/messages", json={"body_md": "Zweite"})
    assert r.status_code == 201 and r.json()["agent_run"]["id"] is None, r.text  # no run
    await _set(real_db, first, state=RunState.RUNNING, wait_until=None, lease_until=lease)
    return owner, dm_id, first


@asynccontextmanager
async def _ending(real_db: RealDb, run_id: uuid.UUID) -> AsyncIterator[tuple[AsyncSession, Run]]:
    """The run's closing transaction, its row locked as in every step."""
    async with real_db.database.session_factory() as session, session.begin():
        run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
        assert run is not None
        yield session, run


async def _close(session: AsyncSession, run: Run) -> None:
    await close(session, RunSteps(session, Claimed.of(run)), run, StopReason.COMPLETED, "Erste")


async def _follow_up(real_db: RealDb, first: uuid.UUID) -> Run:
    async with real_db.database.session_factory() as session:
        later = await session.scalar(select(Run).where(Run.id != first))
        assert later is not None  # the follow-up for "Zweite"
        return later


async def _cancelled_with_notice(real_db: RealDb, dm_id: str, run: Run) -> None:
    async with real_db.database.session_factory() as session:
        found = await session.get_one(Run, run.id, populate_existing=True)
        assert (found.state, found.stop_reason) == (RunState.DONE, StopReason.CANCELLED)
        notices = await session.scalars(
            select(Message.body_md).where(
                Message.conversation_id == uuid.UUID(dm_id),
                Message.kind == MessageKind.SYSTEM,
                Message.created_at >= run.created_at,
            )
        )
        stops = [json.loads(n) for n in notices]
        assert any(s.get("to") == "cancelled" for s in stops), stops


async def test_a_fresh_start_after_the_follow_up_is_queued_cancels_it(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    owner, dm_id, first = await _second_unanswered(real_db, make_real_client, openai_stub)
    version = await _version(owner, dm_id)
    fresh = None
    try:
        async with _ending(real_db, first) as (session, run):
            await _close(session, run)  # queues the follow-up, holding the DM's row
            fresh = asyncio.create_task(
                owner.post(f"/api/conversations/{dm_id}/fresh-start", json={"version": version})
            )
            await _waits_or_done(real_db, fresh)
            assert not fresh.done()  # it waits for the closing transaction
    finally:
        if fresh is not None:
            await asyncio.wait({fresh})
    assert fresh is not None
    assert fresh.result().status_code == 200, fresh.result().text
    await _cancelled_with_notice(real_db, dm_id, await _follow_up(real_db, first))
    assert await _claimed(real_db) is None  # nothing left to run after the cut


async def test_a_fresh_start_before_the_follow_up_gives_way_and_cancels_it_when_pressed_again(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    owner, dm_id, first = await _second_unanswered(real_db, make_real_client, openai_stub)
    version = await _version(owner, dm_id)
    fresh = None
    try:
        async with _ending(real_db, first) as (session, run):
            fresh = asyncio.create_task(
                owner.post(f"/api/conversations/{dm_id}/fresh-start", json={"version": version})
            )
            await _waits_or_done(real_db, fresh)  # it holds the DM and waits for the run
            await _close(session, run)  # waits for the DM's row until the fresh start yields
    finally:
        if fresh is not None:
            await asyncio.wait({fresh})
    assert fresh is not None
    r = fresh.result()
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict.retry", r.text
    later = await _follow_up(real_db, first)
    assert later.state == RunState.QUEUED
    again = await owner.post(
        f"/api/conversations/{dm_id}/fresh-start", json={"version": await _version(owner, dm_id)}
    )
    assert again.status_code == 200, again.text
    await _cancelled_with_notice(real_db, dm_id, later)
