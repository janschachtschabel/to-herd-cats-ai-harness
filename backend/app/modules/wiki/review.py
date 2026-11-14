"""Page review (plan M7 decision 11, spec 9 "Veraltete Seiten"): a space may set a
review interval (`space.review_interval_days`, 7 to 730 days; off by default, set by
those who manage the space). A published page is reviewed when it is published and
whenever someone who may edit it marks it as reviewed (`page.reviewed_at`); once the
interval has passed since, its review is due (the rule: `review_repository.due_pages`).

- The API shows `reviewed_at` and `review_due` on every page, `review_due` on the
  tree's pages, and filters the tree to due pages (`due_filter`).
- "Mark as reviewed" (`mark_reviewed`): `page.edit` in the space, a published page
  (409 `page.not_published` for a draft); a page the actor cannot see is 404. It
  takes no `version` and bumps none: it changes nothing of the page, and racing marks
  end the same way. Audited (`page.reviewed`).
- The daily pass (`review_pass.py`) emits `page.review_due` once per interval for
  each due page; a handler turns it into an activity entry for the space's
  moderators (`review_handlers.py`).
"""

import uuid
from collections.abc import Collection

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.errors import Conflict
from app.modules.audit.recorder import record
from app.modules.wiki.models import Page, PageStatus
from app.modules.wiki.review_repository import ReviewRepository
from app.modules.wiki.visibility import PageReader


class ReviewService:
    def __init__(self, session: AsyncSession, clock: Clock = SYSTEM_CLOCK) -> None:
        self.session = session
        self.clock = clock
        self.reviews = ReviewRepository(session)

    async def due_among(self, actor: Actor, page_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Those of the pages (which the caller has shown the actor) that are due."""
        return await self.reviews.due_among(actor.org_id, page_ids, self.clock.now())

    def due_filter(self, actor: Actor, space_id: uuid.UUID) -> Select[uuid.UUID]:
        """The ids of the space's due pages, for the tree (which applies the rights)."""
        return self.reviews.due_in(actor.org_id, space_id, self.clock.now())

    async def mark_reviewed(self, actor: Actor, page_id: uuid.UUID) -> Page:
        reader = PageReader(self.session)
        page = await reader.readable(actor, page_id, lock=True)
        await reader.require_in_space(actor, Action.PAGE_EDIT, page)
        if page.status != PageStatus.PUBLISHED:
            raise Conflict(code="page.not_published")
        await self.reviews.mark_reviewed(actor.org_id, page.id, self.clock.now())
        await record(self.session, actor, "page.reviewed", "page", page.id)
        await self.session.refresh(page)
        return page
