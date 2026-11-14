"""The stuck-run gauge (`herd_runs_stuck`, alert `HerdRunsStuck`): a running run counts
when its lease ran out, or when its current take-up (`taken_at`) began longer ago than
any run may run. A run's first start (`started_at`) does not count: a run resumed
after waiting hours for a person is healthy."""

from datetime import timedelta

from sqlalchemy import update

from app.core.models_base import utcnow
from app.modules.agents.executor_repository import claim
from app.modules.agents.gauge_repository import STUCK_GRACE_SECONDS, open_runs
from app.modules.agents.models import MAX_RUNTIME_SECONDS, Run
from tests.factories_agents import LEASE, Bench


async def test_a_run_resumed_after_a_long_wait_is_not_stuck(bench: Bench) -> None:
    await bench.say("Hallo")
    async with bench.unit()() as session:
        claimed = await claim(session, LEASE)
    assert claimed is not None
    # As after a resume: first started long ago (it waited), taken up now, lease fresh.
    await bench.session.execute(
        update(Run).where(Run.id == claimed.id).values(started_at=utcnow() - timedelta(hours=2))
    )
    run = await bench.run_of(claimed.id)
    assert run.lease_until is not None and run.lease_until > utcnow()
    assert (await open_runs(bench.session)).stuck == 0


async def test_a_take_up_older_than_any_run_may_run_is_stuck(bench: Bench) -> None:
    """Even with a lease someone keeps renewing."""
    await bench.say("Hallo")
    async with bench.unit()() as session:
        claimed = await claim(session, LEASE)
    assert claimed is not None
    overdue = timedelta(seconds=MAX_RUNTIME_SECONDS + STUCK_GRACE_SECONDS + 5)
    await bench.session.execute(
        update(Run).where(Run.id == claimed.id).values(taken_at=utcnow() - overdue)
    )
    assert (await bench.run_of(claimed.id)).lease_until > utcnow()  # type: ignore[operator]
    assert (await open_runs(bench.session)).stuck == 1


async def test_every_take_up_sets_its_time(bench: Bench) -> None:
    await bench.say("Hallo")
    async with bench.unit()() as session:
        first = await claim(session, LEASE)
    assert first is not None
    long_ago = utcnow() - timedelta(hours=1)
    await bench.session.execute(
        update(Run)
        .where(Run.id == first.id)
        .values(taken_at=long_ago, started_at=long_ago, lease_until=utcnow() - timedelta(seconds=1))
    )
    async with bench.unit()() as session:
        again = await claim(session, LEASE)  # its worker died: taken up again
    assert again is not None and again.id == first.id and again.attempt == 2
    run = await bench.run_of(first.id)
    assert run.started_at == long_ago  # the first start stays
    assert run.taken_at is not None and run.taken_at > utcnow() - timedelta(minutes=1)
