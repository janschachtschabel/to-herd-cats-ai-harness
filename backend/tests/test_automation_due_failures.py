"""A term that cannot fire holds nobody else (review M7, finding 3). `claim_due` takes
the most overdue term first; a term whose transaction fails would stay the most
overdue, so the due loop sets that automation aside (`firing.set_aside`: its next
term a backoff later, 1, 2, 4 … minutes, at most an hour; `term_errors` counts the
streak, the API shows it, the metric counts each) and goes on with the next term in
the same pass. A logged term ends the streak. The page review and the cleanup run in
every round, whatever the firing did; a space whose review step fails is passed over
for the rest of the round."""

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest

from app.core.metrics import REGISTRY
from app.modules.automations import firing
from app.modules.automations.models import Automation
from app.modules.wiki import review_pass
from app.worker.due import DueLoop
from tests.factories_automations import automation_row, firings
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.support.openai_stub import OpenAIStub
from tests.test_automation_due_loop import T0, _place


async def _two(real_db: RealDb, place: dict[str, Any]) -> tuple[uuid.UUID, uuid.UUID]:
    """A broken automation (the most overdue) and a healthy one, committed."""
    async with real_db.database.session_factory() as session:
        args = (place["org"], place["owner"], place["agent"], place["dm"])
        broken = automation_row(*args, due=T0 - timedelta(hours=1))
        healthy = automation_row(*args, due=T0)
        session.add_all([broken, healthy])
        await session.commit()
        return broken.id, healthy.id


def _break(monkeypatch: pytest.MonkeyPatch, broken_id: uuid.UUID) -> list[bool]:
    """Make the broken automation's term fail (any bug or bad row); a switch to heal it."""
    original, healed = firing.fire, [False]

    async def fire(session: Any, automation: Automation, due_at: datetime, now: datetime) -> Any:
        if automation.id == broken_id and not healed[0]:
            raise RuntimeError("this term cannot fire")
        return await original(session, automation, due_at, now)

    monkeypatch.setattr(firing, "fire", fire)
    return healed


async def _row(real_db: RealDb, automation_id: uuid.UUID) -> Automation:
    async with real_db.database.session_factory() as session:
        found = await session.get(Automation, automation_id)
        assert found is not None
        return found


def _set_aside() -> float:
    return REGISTRY.get_sample_value("herd_automation_terms_set_aside_total") or 0.0


async def test_one_term_that_fails_does_not_hold_the_others(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    broken_id, healthy_id = await _two(real_db, place)
    _break(monkeypatch, broken_id)
    loop = DueLoop(real_db.database, clock=SettableClock(T0 + timedelta(seconds=1)))
    for _ in range(5):  # as `_serve` does: a failed pass is tried again
        try:
            await loop.round()
        except RuntimeError:
            pass
    async with real_db.database.session_factory() as session:
        fired = [f.outcome for f in await firings(session, healthy_id)]
    assert fired == ["started"], "the healthy automation never fired behind the broken one"


async def test_a_failing_term_backs_off_boundedly_and_a_fired_one_ends_the_streak(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    broken_id, _ = await _two(real_db, place)
    healed = _break(monkeypatch, broken_id)
    clock = SettableClock(T0)
    loop = DueLoop(real_db.database, clock=clock)
    before = _set_aside()
    waits = []
    for _ in range(9):
        await loop.pass_once()  # never raises for a term it could set aside
        row = await _row(real_db, broken_id)
        assert row.next_due_at is not None
        waits.append(row.next_due_at - clock.now())
        clock.set(row.next_due_at)
    minutes = [int(w.total_seconds() // 60) for w in waits]
    assert minutes == [1, 2, 4, 8, 16, 32, 60, 60, 60]
    assert (await _row(real_db, broken_id)).term_errors == 9
    assert _set_aside() - before == 9
    healed[0] = True
    await loop.pass_once()
    row = await _row(real_db, broken_id)
    assert row.term_errors == 0
    async with real_db.database.session_factory() as session:
        assert [f.outcome for f in await firings(session, broken_id)] == ["started"]


async def test_the_review_and_the_cleanup_run_though_the_firing_fails(
    real_db: RealDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure before any term was claimed (the claim itself) is not set aside: the
    round still takes its review steps and its cleanup, then the error goes to
    `_serve`, which waits and tries again."""
    ran: list[str] = []

    async def claim_fails(*_: Any, **__: Any) -> None:
        raise RuntimeError("the claim failed")

    async def review_once(self: DueLoop) -> int:
        ran.append("review")
        return 0

    async def cleanup_if_due(self: DueLoop) -> None:
        ran.append("cleanup")

    monkeypatch.setattr(firing, "claim_due", claim_fails)
    monkeypatch.setattr(DueLoop, "review_once", review_once)
    monkeypatch.setattr(DueLoop, "cleanup_if_due", cleanup_if_due)
    loop = DueLoop(real_db.database, clock=SettableClock(T0))
    with pytest.raises(RuntimeError):
        await loop.round()
    assert ran == ["review", "cleanup"]


async def test_a_space_whose_review_fails_is_passed_over_for_the_round(
    real_db: RealDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_wiki_review_workers import T0 as AT
    from tests.test_wiki_review_workers import _reminded, _spaces

    due_pages = await _spaces(real_db, spaces=2, pages=1)
    original = review_pass.ReviewRepository.remind
    failing: list[uuid.UUID] = []

    async def remind(self: Any, space_id: uuid.UUID, now: datetime, limit: int) -> Any:
        if not failing:
            failing.append(space_id)  # the first space claimed cannot be reviewed
        if space_id in failing:
            raise RuntimeError("this space cannot be reviewed")
        return await original(self, space_id, now, limit)

    monkeypatch.setattr(review_pass.ReviewRepository, "remind", remind)
    loop = DueLoop(real_db.database, clock=SettableClock(AT + timedelta(minutes=1)))
    assert await loop.review_once() == 1  # the other space, in the same round
    assert sum((await _reminded(real_db)).values()) == len(due_pages) - 1
