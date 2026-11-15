"""The wiki's outbox events (spec 4.3, plan M3 task 8): written by the page services in
the transaction of the change, so an event exists exactly when its change committed.

Events with a place on the page's timeline (`messaging.threads.page_timeline` writes a
system message into the page's thread for each):

- `page.created`, `page.published`, `page.moved`, `page.trashed`, `page.restored`
  (from the trash), `page.version_restored` (payload also `number`).

`page.review_due` (plan M7 decision 11) comes from the worker's daily pass
(`review_pass.py`), not from a change: once per interval for a page whose review is
due. Its actor is whoever last wrote the page (nobody causes it). Its handler
(`review_handlers.py`) writes its timeline entry and the moderators' activity, so it
is not among `PAGE_EVENTS`; automations' event rules subscribe to it (plan M7 task 5).

`attachment.uploaded` (plan M7 task 5): an upload through the route (subject: the
attachment; payload `attachment_id`, `page_id`); for automations' event rules, on no
timeline.

Content changes emit nothing: they are too many, and the versions show them. Payloads
hold ids and numbers, never titles, paths or content. Subject: the page; space: its
space.

An import emits no events (only its audit entry `space.imported`): thousands of pages
stay one transaction of a bounded number of statements per page (review M2 R19), and
their threads start empty when first opened. (An import event nobody read was dropped
in M4: imported pages get no timeline entries.)
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.outbox import emit
from app.modules.wiki.models import Page

PAGE_CREATED = "page.created"
PAGE_PUBLISHED = "page.published"
PAGE_MOVED = "page.moved"
PAGE_TRASHED = "page.trashed"
PAGE_RESTORED = "page.restored"
PAGE_VERSION_RESTORED = "page.version_restored"
PAGE_REVIEW_DUE = "page.review_due"
ATTACHMENT_UPLOADED = "attachment.uploaded"

PAGE_EVENTS = (
    PAGE_CREATED,
    PAGE_PUBLISHED,
    PAGE_MOVED,
    PAGE_TRASHED,
    PAGE_RESTORED,
    PAGE_VERSION_RESTORED,
)


async def page_event(
    session: AsyncSession, actor: Actor, type_: str, page: Page, **extra: Any
) -> None:
    """Emit `type_` about `page` (`extra`: numbers or flags only)."""
    await emit(
        session,
        type=type_,
        actor=actor,
        space_id=page.space_id,
        subject_type="page",
        subject_id=page.id,
        payload={"page_id": str(page.id), **extra},
    )
