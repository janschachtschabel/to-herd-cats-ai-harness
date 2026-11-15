"""Module review M8 4, K4: "Neu beginnen" against a message sent at the same moment,
with real commits on two connections (`tests/real_db.py`). The fresh start and a
person's new message in the DM serialise on the conversation's row (`FOR NO KEY
UPDATE` against `FOR SHARE`), and the cut is taken from the database's clock, at or
after everything the DM held when it was taken. So a run created before the cut is
cancelled with its notice, and a message after it is answered by a run that reads it,
whatever the API node's clock says; none ends silently.

Each test fixes the order: the first transaction is open, the second is started and
runs until Postgres shows it waiting on a lock (or it finished, which is the bug),
then the first commits. No sleeps."""

import asyncio
import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select, text

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
import app.modules.messaging.dating as message_dating
from app.core.models_base import utcnow
from app.modules.agents.executor import Executor
from app.modules.agents.fresh_start import start_afresh
from app.modules.agents.run_models import Run, StopReason
from app.modules.agents.step_host import units_of
from app.modules.audit.models import AuditLog
from app.modules.messaging.models import Conversation, Message, MessageKind
from app.modules.messaging.service import MessageService
from app.modules.users.models import User
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of
from tests.test_run_cancel_races import _claimed, _dm

LOCKS = text(
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
)
POLLS = 5_000  # each poll is a round trip to Postgres, never a sleep


async def _waits_or_done(real_db: RealDb, task: asyncio.Task[Any]) -> None:
    """Until the task waits on a row lock, or it has finished (it did not wait)."""
    for _ in range(POLLS):
        if task.done():
            return
        async with real_db.database.session_factory() as session:
            if await session.scalar(LOCKS):
                return
    raise AssertionError("the second transaction neither waited nor finished")


async def _owner(session: Any, real_db: RealDb) -> Any:
    user = await session.scalar(select(User).where(User.email == real_db.owner_email))
    assert user is not None
    return await actor_of(session, user)


async def _version(client: Any, dm_id: str) -> int:
    return int((await client.get(f"/api/conversations/{dm_id}")).json()["version"])


def _clock_off(monkeypatch: Any, by: timedelta) -> None:
    """The API node's clock, as messages take it, is `by` off the database's."""
    monkeypatch.setattr(message_dating, "utcnow", lambda: utcnow() + by)


async def test_a_message_before_the_cut_has_its_run_cancelled_with_a_notice(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub, monkeypatch: Any
) -> None:
    owner, dm_id, _ = await _dm(real_db, make_real_client, openai_stub)
    version = await _version(owner, dm_id)
    _clock_off(monkeypatch, timedelta(minutes=1))  # ahead: the message looks later
    fresh = None
    try:
        async with real_db.database.session_factory() as first, first.begin():
            posted = await MessageService(first).post(
                await _owner(first, real_db), uuid.UUID(dm_id), "Vorher"
            )
            assert posted.agent_run is not None and posted.agent_run.run_id is not None
            run_id = posted.agent_run.run_id
            fresh = asyncio.create_task(
                owner.post(f"/api/conversations/{dm_id}/fresh-start", json={"version": version})
            )
            await _waits_or_done(real_db, fresh)
    finally:
        if fresh is not None:
            await asyncio.wait({fresh})
    assert fresh is not None
    r = fresh.result()
    assert r.status_code == 200, r.text
    async with real_db.database.session_factory() as session:
        run = await session.get_one(Run, run_id)
        assert (run.state, run.stop_reason) == ("done", StopReason.CANCELLED)
        notices = await session.scalars(
            select(Message.body_md).where(
                Message.conversation_id == uuid.UUID(dm_id), Message.kind == MessageKind.SYSTEM
            )
        )
        stops = [json.loads(n) for n in notices]
        assert {"key": "run.stopped", "to": "cancelled"}.items() <= stops[0].items(), stops
        cut = await session.scalar(
            select(Conversation.fresh_start_at).where(Conversation.id == uuid.UUID(dm_id))
        )
        said = await session.scalar(select(Message.created_at).where(Message.body_md == "Vorher"))
        assert cut is not None and said is not None and said <= cut  # before the cut
        audit = await session.scalar(
            select(AuditLog.details).where(AuditLog.action == "conversation.fresh_start")
        )
        assert audit == {"cancelled_runs": 1}


async def test_a_message_after_the_cut_is_answered_by_a_run_that_reads_it(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub, monkeypatch: Any
) -> None:
    owner, dm_id, _ = await _dm(real_db, make_real_client, openai_stub)
    version = await _version(owner, dm_id)
    _clock_off(monkeypatch, -timedelta(minutes=1))  # behind: the message looks earlier
    posting = None
    try:
        async with real_db.database.session_factory() as first, first.begin():
            await start_afresh(first, await _owner(first, real_db), uuid.UUID(dm_id), version)
            body = {"body_md": "Nachher"}
            posting = asyncio.create_task(
                owner.post(f"/api/conversations/{dm_id}/messages", json=body)
            )
            await _waits_or_done(real_db, posting)
    finally:
        if posting is not None:
            await asyncio.wait({posting})
    assert posting is not None
    r = posting.result()
    assert r.status_code == 201 and r.json()["agent_run"]["id"], r.text
    openai_stub.state.replies.append({"content": "Antwort nach dem Schnitt"})
    before = len(openai_stub.state.log)
    executor = Executor(units_of(real_db.database.session_factory))
    assert await executor.execute(await _claimed(real_db)) == StopReason.COMPLETED
    asked = [str(e.body) for e in openai_stub.state.log[before:]]
    assert asked and "Nachher" in asked[0]  # the run reads the message it answers
    async with real_db.database.session_factory() as session:
        answers = await session.scalars(
            select(Message.body_md).where(
                Message.conversation_id == uuid.UUID(dm_id), Message.kind == MessageKind.AGENT
            )
        )
        assert list(answers) == ["Antwort nach dem Schnitt"]
