"""The SQL of page review (plan M7 decision 11, `review.py`, `review_pass.py`).

The one rule, `due_pages(now)`, in whole UTC days: a page last reviewed on day D (UTC) in a
space with an interval of N days is due from 0:00 UTC of day D + N, whatever the hour
it was reviewed at, so the daily pass, which runs early in the day, finds it on that
day. Only published pages outside the trash, in a space whose interval is set, and
never an agent's memory: a page named by `agent_memory`, nor the memory folders
`_agenten/…` (whose paths a title never gives). The same cutoff decides whether
`page.review_due` may be emitted again for a page whose last one went unanswered:
once per interval (`not_reminded`). Statements that take an organisation start
from it; the daily pass works across organisations, one space at a time.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import (
    ColumnElement,
    DateTime,
    Select,
    and_,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal, PrincipalType
from app.core.repository import locked_batch
from app.modules.agents.memory_models import MEMORY_FOLDER_SLUG, AgentMemory
from app.modules.spaces.models import Space
from app.modules.wiki.models import Page, PageStatus


def _cutoff(now: datetime) -> ColumnElement[datetime]:
    """Reviews (or reminders) before this are N days old at `now`: 0:00 UTC of
    tomorrow, less N whole days (hours: no time zone moves them)."""
    tomorrow = datetime.combine(now.astimezone(UTC).date(), time(), tzinfo=UTC)
    tomorrow += timedelta(days=1)
    hours = Space.review_interval_days * 24
    return literal(tomorrow, DateTime(timezone=True)) - func.make_interval(0, 0, 0, 0, hours)


def _memory() -> ColumnElement[bool]:
    folder = MEMORY_FOLDER_SLUG
    return or_(
        exists().where(AgentMemory.org_id == Page.org_id, AgentMemory.page_id == Page.id),
        Page.path == folder,
        Page.path.startswith(f"{folder}/", autoescape=True),
    )


def due_pages(now: datetime) -> Select[uuid.UUID]:
    """The ids of the pages due for review at `now`, joined with their spaces (which
    `not_reminded` reads too)."""
    space = and_(Space.id == Page.space_id, Space.org_id == Page.org_id)
    return select(Page.id).join(Space, space).where(_due(now))


def _due(now: datetime) -> ColumnElement[bool]:
    return and_(
        Space.review_interval_days.is_not(None),
        Page.status == PageStatus.PUBLISHED,
        Page.trashed_at.is_(None),
        Page.reviewed_at < _cutoff(now),
        ~_memory(),
    )


def not_reminded(now: datetime) -> ColumnElement[bool]:
    """No `page.review_due` for the page within its interval (in `due_pages`)."""
    return or_(Page.review_notified_at.is_(None), Page.review_notified_at < _cutoff(now))


@dataclass(frozen=True, slots=True)
class Reminded:
    """A page the pass marked reminded: what its event names. `writer`: who last wrote
    the page, the event's actor (nobody causes a review to come due)."""

    org_id: uuid.UUID
    space_id: uuid.UUID
    page_id: uuid.UUID
    writer: Principal


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- the API ---------------------------------------------------------------------

    def due_in(self, org_id: uuid.UUID, space_id: uuid.UUID, now: datetime) -> Select[uuid.UUID]:
        """The ids of the space's pages due at `now` (for the tree's filter)."""
        return due_pages(now).where(Page.org_id == org_id, Page.space_id == space_id)

    async def due_among(
        self, org_id: uuid.UUID, page_ids: Collection[uuid.UUID], now: datetime
    ) -> set[uuid.UUID]:
        """Those of the pages that are due at `now`."""
        if not page_ids:
            return set()
        stmt = due_pages(now).where(Page.org_id == org_id, Page.id.in_(list(page_ids)))
        return set(await self.session.scalars(stmt))

    async def mark_reviewed(self, org_id: uuid.UUID, page_id: uuid.UUID, at: datetime) -> None:
        """Reviewed now; reminders start again. Neither `version` nor `updated_at`
        moves: nothing of the page changed."""
        stmt = (
            update(Page)
            .where(Page.org_id == org_id, Page.id == page_id)
            .values(reviewed_at=at, review_notified_at=None, updated_at=Page.updated_at)
        )
        await self.session.execute(stmt)

    # --- the daily pass ----------------------------------------------------------------

    async def claim_space(
        self, today: date, skip: Collection[uuid.UUID] = ()
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        """A space (org id, space id) with an interval that the pass has not been
        through today, locked until the transaction ends; spaces another worker holds,
        and those in `skip`, are passed over. `FOR NO KEY UPDATE` leaves inserts that
        refer to the space (pages, messages) free."""
        stmt = (
            select(Space.org_id, Space.id)
            .where(
                Space.review_interval_days.is_not(None),
                or_(Space.review_checked_on.is_(None), Space.review_checked_on < today),
                Space.id.not_in(list(skip)),
            )
            .order_by(Space.review_checked_on.nulls_first(), Space.id)
            .limit(1)
            .with_for_update(key_share=True, skip_locked=True)
        )
        row = (await self.session.execute(stmt)).first()
        return (row[0], row[1]) if row is not None else None

    async def reminded_since(self, space_id: uuid.UUID, since: datetime) -> int:
        """How many of the space's pages were reminded at or after `since`."""
        stmt = select(func.count()).where(
            Page.space_id == space_id, Page.review_notified_at >= since
        )
        return int(await self.session.scalar(stmt) or 0)

    async def remind(self, space_id: uuid.UUID, now: datetime, limit: int) -> list[Reminded]:
        """Up to `limit` of the space's due pages that had no reminder within their
        interval, those reviewed longest ago first, marked reminded at `now`, by id.
        The pages are locked (waiting for a writer that holds one: skipping it would
        lose it until the next day); the space's own lock keeps other workers out."""
        batch = locked_batch(
            due_pages(now)
            .where(Page.space_id == space_id, not_reminded(now))
            .order_by(Page.reviewed_at.nulls_first(), Page.id)
            .limit(limit)
            .with_for_update(of=Page)
            .correlate(None),  # its own `page`, not the UPDATE's
            "due_pages",
        )
        stmt = (
            update(Page)
            .where(Page.id == batch.c.id)
            .values(review_notified_at=now, updated_at=Page.updated_at)
            .returning(
                Page.org_id, Page.space_id, Page.id, Page.updated_by_type, Page.updated_by_id
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return sorted(
            (Reminded(o, s, p, Principal(PrincipalType(t), w)) for o, s, p, t, w in rows),
            key=lambda r: r.page_id,
        )

    async def unchecked(self, today: date) -> int:
        """How many spaces with an interval the pass has not been through today, across
        organisations (the worker's gauge)."""
        stmt = select(func.count()).where(
            Space.review_interval_days.is_not(None),
            or_(Space.review_checked_on.is_(None), Space.review_checked_on < today),
        )
        return int(await self.session.scalar(stmt) or 0)

    async def checked(self, space_id: uuid.UUID, today: date) -> None:
        """The pass went through the space today."""
        stmt = update(Space).where(Space.id == space_id).values(review_checked_on=today)
        await self.session.execute(stmt)
