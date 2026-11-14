"""A fired term changes what the lists show (its last run, its next term), so each
term the due loop or an event rule logs writes one `automation.updated` (ids only),
which the worker turns into `automation.changed` for who sees it (`live.py`): one
per term, whatever its outcome, and none for an event counted within a quiet time."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.outbox import EventOutbox
from app.modules.automations.live import CHANGED
from app.modules.automations.models import FiringOutcome
from tests.factories_automations import T0, beating, fire, firings, placed, ruled
from tests.factories_writing import Work
from tests.test_automation_events import QUIET, _channel, take_in


async def told(work: Work, automation_id: uuid.UUID) -> list[EventOutbox]:
    stmt = (
        select(EventOutbox)
        .where(EventOutbox.type == CHANGED, EventOutbox.subject_id == automation_id)
        .order_by(EventOutbox.id)
    )
    return list((await work.bench.session.scalars(stmt)).all())


async def test_each_term_of_the_due_loop_writes_one_event(work: Work) -> None:
    bench = work.bench
    automation = await placed(bench, bench.dm_id)
    started = await fire(bench, T0)
    assert started.outcome == FiringOutcome.STARTED
    assert len(await told(work, automation.id)) == 1
    busy = await fire(bench, T0 + timedelta(hours=1))  # the first run is still open
    assert busy.outcome == FiringOutcome.SKIPPED_BUSY
    rows = await told(work, automation.id)
    assert len(rows) == 2
    for row in rows:
        assert row.payload == {"automation_id": str(automation.id)}
        assert row.space_id is None  # a DM


async def test_a_heartbeat_skipped_after_its_window_writes_one_too(work: Work) -> None:
    bench = work.bench
    automation = await beating(bench, bench.dm_id, due=T0.replace(hour=15, minute=55))
    fired = await fire(bench, T0.replace(hour=19))
    assert fired.outcome == FiringOutcome.SKIPPED_OFF_HOURS
    assert len(await told(work, automation.id)) == 1


async def test_an_event_rule_writes_one_per_term_and_none_per_counted_event(
    work: Work,
) -> None:
    bench, channel = work.bench, await _channel(work)
    rule = await ruled(bench, channel)
    await work.ticket("Erstes")
    await take_in(bench, "ticket.created", T0)
    rows = await told(work, rule.id)
    assert [r.space_id for r in rows] == [work.space.id]
    for second in (10, 20, 30):  # within the quiet time: counted, no term
        await work.ticket(f"Später {second}")
        await take_in(bench, "ticket.created", T0 + timedelta(seconds=second))
    assert len(await told(work, rule.id)) == 1
    await fire(bench, T0 + timedelta(seconds=QUIET))
    assert len(await told(work, rule.id)) == 2
    assert len(await firings(bench.session, rule.id)) == 2
