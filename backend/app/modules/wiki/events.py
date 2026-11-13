"""The wiki's outbox events (spec 4.3, plan M3 task 8): written by the page services in
the transaction of the change, so an event exists exactly when its change committed.

Events with a place on the page's timeline (`messaging.threads.page_timeline` writes a
system message into the page's thread for each):

- `page.created`, `page.published`, `page.moved`, `page.trashed`, `page.restored`
  (from the trash), `page.version_restored` (payload also `number`).

Content changes emit nothing: they are too many, and the versions show them. Payloads
hold ids and numbers, never titles, paths or content. Subject: the page; space: its
space.

An import emits one `space.imported` (subject the space, payload `created`) instead of
an event per page: thousands of pages stay one transaction of a bounded number of
statements per page (review M2 R19), and their threads start empty when first opened.
"""

import uuid
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
SPACE_IMPORTED = "space.imported"

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


async def space_imported(
    session: AsyncSession, actor: Actor, space_id: uuid.UUID, created: int
) -> None:
    await emit(
        session,
        type=SPACE_IMPORTED,
        actor=actor,
        space_id=space_id,
        subject_type="space",
        subject_id=space_id,
        payload={"space_id": str(space_id), "created": created},
    )
