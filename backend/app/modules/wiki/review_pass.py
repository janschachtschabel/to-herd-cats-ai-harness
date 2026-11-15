"""The daily pass of page review (plan M7 decision 11), driven by the worker's due loop
(`app/worker/due.py`) beside the automations, exactly once across any number of
workers.

One step (`review_next`, in the caller's transaction) claims one space that has an
interval and that the pass has not been through today (UTC; `space.review_checked_on`)
with `FOR NO KEY UPDATE SKIP LOCKED`, so no two workers are in the same space at once;
marks up to `batch` of its due pages reminded (`page.review_notified_at`, see
`review_repository.due_pages` and `not_reminded`), those reviewed longest ago first,
and emits `page.review_due` for each (ids only); and, when that was the last of them
or the space had its DAILY_REMINDERS today (review M7, finding 12: an interval set
for the first time makes every old page due at once), notes the space as checked
today. The rest follow on later days; the tree's filter shows every due page.
A space with many due pages takes several steps, each its own short transaction;
until the last one it stays unchecked, and the next step (here or in another worker)
claims it again. A step that fails leaves nothing behind: its pages stay unreminded
and the space unchecked; the due loop passes that space over for the rest of its
round (`skip`), so one space that cannot be reviewed holds no other.

Why a date on the space and no job table or automation row: automations belong to
people (decision 2), and a single job row would make one worker do every
organisation's spaces at once; the date is per space, scoped by its organisation,
and costs one indexed look per round once every space is done. What makes a reminder
happen once is the page row itself: its lock, and the reminder time written with the
event in one transaction. Changing a space's interval clears its date, so the next
round looks at it again (a shorter interval makes pages due at once).
"""

import uuid
from collections import defaultdict
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventActor, NewEvent, emit_many
from app.core.principal import Principal
from app.modules.wiki.events import PAGE_REVIEW_DUE
from app.modules.wiki.review_repository import Reminded, ReviewRepository

BATCH = 100  # pages per step (transaction)
DAILY_REMINDERS = 20  # pages of one space reminded per UTC day, oldest review first


@dataclass(frozen=True, slots=True)
class Step:
    space_id: uuid.UUID
    reminded: int  # pages reminded (events emitted) in this step
    done: bool  # the space is checked for today


async def review_next(
    session: AsyncSession,
    now: datetime,
    *,
    batch: int = BATCH,
    skip: Collection[uuid.UUID] = (),
    claimed: Callable[[uuid.UUID], None] | None = None,
) -> Step | None:
    """One step of the pass at `now`; None when every space is checked for today (or
    held by another worker). `skip`: spaces to pass over (their step failed in this
    round); `claimed` hears of the space taken."""
    reviews = ReviewRepository(session)
    today = now.astimezone(UTC).date()
    found = await reviews.claim_space(today, skip)
    if found is None:
        return None
    org_id, space_id = found
    if claimed is not None:
        claimed(space_id)
    already = await reviews.reminded_since(space_id, datetime.combine(today, time(), UTC))
    limit = min(batch, max(DAILY_REMINDERS - already, 0))
    reminded = await reviews.remind(space_id, now, limit) if limit else []
    await _emit(session, org_id, reminded)
    done = len(reminded) < limit or already + len(reminded) >= DAILY_REMINDERS
    if done:
        await reviews.checked(space_id, today)
    return Step(space_id, len(reminded), done)


async def _emit(session: AsyncSession, org_id: uuid.UUID, reminded: list[Reminded]) -> None:
    """`page.review_due` per page (payload `page_id`, like the other page events). Its
    actor is whoever last wrote the page: nobody causes a review to come due, and the
    events name no one else (one INSERT per writer)."""
    by_writer: dict[Principal, list[NewEvent]] = defaultdict(list)
    for page in reminded:
        by_writer[page.writer].append(
            NewEvent(
                type=PAGE_REVIEW_DUE,
                space_id=page.space_id,
                subject_type="page",
                subject_id=page.page_id,
                payload={"page_id": str(page.page_id)},
            )
        )
    for writer, events in by_writer.items():
        await emit_many(session, actor=EventActor(org_id, writer), events=events)
