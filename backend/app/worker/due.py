"""The worker's due loop (plan M7 decision 1): automations whose term has come fire
here, exactly once across any number of workers, without DBOS.

Every POLL_SECONDS (and at once after a pass that found work) it fires due
automations one per transaction (`automations.firing.fire_next`: the row locked
`FOR UPDATE SKIP LOCKED`, the run or the skip, the log row and the next term
committed together), at most BATCH per pass, so a stop request is seen between
batches. A transaction that fails (a lost connection, a crash before the commit)
leaves the term due as it was: the next pass, here or in another worker, fires it.
Runs it starts are queued; the run loop takes them up like any other.

Each round also takes steps of the daily page review (`wiki/review_pass.py`), one
transaction each, at most REVIEW_STEPS per round: spaces whose pages it has not been
through today (UTC) are claimed `SKIP LOCKED`, their due pages reminded in batches.

The time comes from a `Clock` (`app.core.clock`); tests set theirs. One database
connection at a time. Outside the worker's readiness, like the run loop.
"""

import asyncio
import logging
from contextlib import suppress

from prometheus_client import Counter

from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.db import Database
from app.core.metrics import REGISTRY
from app.modules.automations.firing import Fired, fire_next
from app.modules.wiki.review_pass import Step, review_next

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0
BATCH = 50
REVIEW_STEPS = 20
MAX_ERROR_WAIT_SECONDS = 30.0

_firings: Counter | None = None


def firings_counter() -> Counter:
    """Registered by the first due loop of a process (an API process exports none)."""
    global _firings  # noqa: PLW0603 -- one registration per process
    if _firings is None:
        _firings = Counter(
            "herd_automation_firings_total",
            "Terms of automations fired by this worker, by outcome.",
            ["outcome"],
            registry=REGISTRY,
        )
    return _firings


class DueLoop:
    def __init__(self, database: Database, *, clock: Clock = SYSTEM_CLOCK) -> None:
        self.database = database
        self.clock = clock
        self.firings = firings_counter()

    async def serve(self, stop: asyncio.Event) -> None:
        failures = 0
        while not stop.is_set():
            more = False
            try:
                more = await self.round()
                failures = 0
            except Exception as exc:  # the term stays due; the next pass fires it
                failures += 1
                logger.warning("automations.pass_failed", extra={"error": type(exc).__name__})
            if more:
                continue  # more may be due
            wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=wait)

    async def round(self) -> bool:
        """Fire due automations, then review steps; whether more may be due."""
        fired = await self.pass_once()
        steps = await self.review_once()
        return fired == BATCH or steps == REVIEW_STEPS

    async def review_once(self) -> int:
        """Steps of the daily page review, one transaction each, until every space is
        checked for today or REVIEW_STEPS were taken; how many."""
        steps = 0
        while steps < REVIEW_STEPS:
            if await self.review_step() is None:
                break
            steps += 1
        return steps

    async def review_step(self) -> Step | None:
        async with self.database.session_factory() as session, session.begin():
            return await review_next(session, self.clock.now())

    async def pass_once(self) -> int:
        """Fire due automations, one transaction each, until none is due or BATCH
        fired; how many fired."""
        fired = 0
        while fired < BATCH:
            found = await self.fire_one()
            if found is None:
                break
            fired += 1
        return fired

    async def fire_one(self) -> Fired | None:
        async with self.database.session_factory() as session, session.begin():
            found = await fire_next(session, self.clock.now())
        if found is not None:  # committed
            self.firings.labels(outcome=found.label).inc()
        return found
