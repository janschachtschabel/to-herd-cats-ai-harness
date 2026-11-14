"""One attempt of a run as the executor works it (`Working`), the units of work its
steps run in, the states that end a take-up without an end (`Lost`, `Suspended`), and
running a step once more after the database rolled it back (`once_more`)."""

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db_errors import is_retryable, sqlstate_of
from app.modules.agents.actor import Reads
from app.modules.agents.executor_repository import Claimed
from app.modules.agents.models import Agent
from app.modules.agents.step_records import restore, snapshot
from app.modules.agents.toolbox.base import ToolSpec

logger = logging.getLogger(__name__)


class Lost(Exception):  # noqa: N818 (a state: the run is no longer this attempt's)
    pass


class Suspended(Exception):  # noqa: N818 (a state: the run waits for a person)
    pass


@dataclass(slots=True)
class Working:
    """One attempt of a run as the executor works it."""

    claimed: Claimed
    agent: Agent
    connection_id: uuid.UUID
    model: str  # the model the calls go to, as at the start (usage is booked on it)
    secret_ref: str | None
    deadline: float
    reads: Reads = field(default_factory=Reads)
    seq: int = 0  # the last recorded; the journal counts on across take-ups
    tools: list[ToolSpec] = field(default_factory=list)  # allowed at the take-up
    reply_to: uuid.UUID | None = None  # the thread it answers in (`place.py`)


Unit = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def units_of(sessions: async_sessionmaker[AsyncSession]) -> Unit:
    """A unit of work per call: a session in a transaction, committed at the end."""

    @asynccontextmanager
    async def unit() -> AsyncIterator[AsyncSession]:
        async with sessions() as session, session.begin():
            yield session

    return unit


async def once_more[T](run: Working, attempt: Callable[[], Awaitable[T]]) -> T:
    """The step, run once more if the database rolled it back as a deadlock's victim or
    on a serialization failure (`runs.step_retried`, the run's id and the SQLSTATE);
    the journal's count and what the run had read are as before the first try."""
    seq, reads = run.seq, snapshot(run.reads)
    try:
        return await attempt()
    except Exception as exc:
        if not is_retryable(exc):
            raise
        run_id, state = str(run.claimed.id), sqlstate_of(exc)
        logger.warning("runs.step_retried", extra={"run_id": run_id, "sqlstate": state})
    run.seq = seq
    restore(run.reads, reads)
    return await attempt()
