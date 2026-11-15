"""The daily page review under real commits (plan M7 task 6): three workers' due loops
on one database, each with connections of its own, remind every due page exactly
once; a space with many due pages goes in several short transactions; a step that
fails leaves nothing behind; a space another worker is in is passed over."""

import asyncio
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import Database
from app.core.outbox import EventOutbox
from app.core.principal import PrincipalType
from app.modules.spaces.models import Space, SpaceKind
from app.modules.users.models import User
from app.modules.wiki.events import PAGE_REVIEW_DUE
from app.modules.wiki.models import Page, PageStatus
from app.modules.wiki.review_pass import review_next
from app.worker.due import DueLoop
from tests.real_db import RealDb
from tests.support.clock import SettableClock

T0 = datetime(2026, 11, 16, 0, 5, tzinfo=UTC)
LOOPS = 3


@pytest.fixture
async def databases(real_db: RealDb) -> AsyncIterator[list[Database]]:
    """One `Database` (engine, pool) per worker."""
    made = [Database(get_settings().test_database_url) for _ in range(LOOPS)]
    yield made
    for database in made:
        await database.dispose()


async def _spaces(real_db: RealDb, spaces: int, pages: int) -> list[uuid.UUID]:
    """Spaces with an interval of 30 days, each with `pages` due pages and one fresh
    one, committed; the due pages' ids."""
    due: list[uuid.UUID] = []
    async with real_db.database.session_factory() as session:
        owner = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert owner is not None
        for s in range(spaces):
            space = Space(
                org_id=owner.org_id, kind=SpaceKind.TEAM, name=f"S{s}", review_interval_days=30
            )
            session.add(space)
            await session.flush()
            for p in range(pages + 1):
                reviewed = T0 - timedelta(days=31 if p < pages else 1)
                page = Page(
                    org_id=owner.org_id,
                    space_id=space.id,
                    title=f"P{p}",
                    slug=f"p{p}",
                    path=f"p{p}",
                    status=PageStatus.PUBLISHED,
                    published_at=reviewed,
                    reviewed_at=reviewed,
                    created_by_type=PrincipalType.USER,
                    created_by_id=owner.id,
                    updated_by_type=PrincipalType.USER,
                    updated_by_id=owner.id,
                )
                session.add(page)
                await session.flush()
                if p < pages:
                    due.append(page.id)
        await session.commit()
    return due


async def _reminded(real_db: RealDb) -> Counter[uuid.UUID]:
    async with real_db.database.session_factory() as session:
        stmt = select(EventOutbox.subject_id).where(EventOutbox.type == PAGE_REVIEW_DUE)
        return Counter((await session.scalars(stmt)).all())


async def _unchecked(real_db: RealDb) -> int:
    async with real_db.database.session_factory() as session:
        stmt = select(func.count()).where(
            Space.review_interval_days.is_not(None), Space.review_checked_on.is_(None)
        )
        return int(await session.scalar(stmt) or 0)


async def test_three_workers_remind_every_due_page_exactly_once(
    real_db: RealDb, databases: list[Database]
) -> None:
    due = await _spaces(real_db, spaces=6, pages=5)
    clock = SettableClock(T0)
    loops = [DueLoop(database, clock=clock) for database in databases]
    await asyncio.gather(*(loop.review_once() for loop in loops))
    assert await _reminded(real_db) == Counter({page_id: 1 for page_id in due})
    assert await _unchecked(real_db) == 0
    # Again the same day, and the next: every worker finds nothing.
    for later in (timedelta(hours=5), timedelta(days=1)):
        clock.set(T0 + later)
        await asyncio.gather(*(loop.review_once() for loop in loops))
        assert await _reminded(real_db) == Counter({page_id: 1 for page_id in due})


async def test_many_due_pages_go_in_several_short_transactions(
    real_db: RealDb, databases: list[Database]
) -> None:
    due = await _spaces(real_db, spaces=1, pages=9)

    async def worker(database: Database) -> int:
        steps = 0
        while True:
            async with database.session_factory() as session, session.begin():
                step = await review_next(session, T0, batch=2)
            if step is None:
                return steps
            steps += 1

    async with databases[0].session_factory() as session, session.begin():
        first = await review_next(session, T0, batch=2)
    assert first is not None and (first.reminded, first.done) == (2, False)
    assert sum((await _reminded(real_db)).values()) == 2  # committed on its own
    assert await _unchecked(real_db) == 1
    steps = await asyncio.gather(*(worker(database) for database in databases))
    assert sum(steps) >= 4  # 7 pages left, 2 per step
    assert await _reminded(real_db) == Counter({page_id: 1 for page_id in due})
    assert await _unchecked(real_db) == 0


async def test_a_failed_step_leaves_nothing_behind(
    real_db: RealDb, databases: list[Database]
) -> None:
    due = await _spaces(real_db, spaces=1, pages=3)
    async with databases[0].session_factory() as session:
        await session.begin()
        step = await review_next(session, T0)
        assert step is not None and step.reminded == 3
        await session.rollback()  # the worker dies before its commit
    assert await _reminded(real_db) == Counter()
    loop = DueLoop(databases[1], clock=SettableClock(T0 + timedelta(minutes=1)))
    assert await loop.review_once() == 1
    assert await _reminded(real_db) == Counter({page_id: 1 for page_id in due})


async def test_a_space_another_worker_is_in_is_passed_over(
    real_db: RealDb, databases: list[Database]
) -> None:
    await _spaces(real_db, spaces=1, pages=2)
    holding = databases[0].session_factory()
    try:
        await holding.begin()
        assert await review_next(holding, T0) is not None  # holds the space, uncommitted
        other = DueLoop(databases[1], clock=SettableClock(T0))
        assert await asyncio.wait_for(other.review_once(), timeout=10) == 0  # no wait
        await holding.commit()
    finally:
        await holding.close()
    assert sum((await _reminded(real_db)).values()) == 2
