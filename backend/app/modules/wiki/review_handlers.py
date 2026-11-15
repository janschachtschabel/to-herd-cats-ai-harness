"""The outbox handler of page review (plan M7 decision 11), registered by name (stored
with each delivery, metric labels); the worker imports this module
(`app/worker/handlers.py`).

`notify_on_review_due`, for `page.review_due` (`review_pass.py`):
- a timeline entry in the page's thread, `{"key": "page.review_due"}` (no actor:
  nobody caused it), referring to its event (`client_id`), emitted as
  `message.created` (flagged `system`) for live delivery;
- `review_due` notifications pointing at that entry for the space's moderators (by
  membership of their own or of a group, holding `page.moderate` there now, as for
  proposals: system admins without such a membership are left out), and only for
  those who may see the page's thread when the handler runs (a moderator who cannot
  see the page gets nothing).

Nothing happens when the page is no longer due for a reminder by then: purged, in
the trash, or reviewed since (its `review_notified_at` cleared). Idempotent: a second
delivery finds its entry (`client_id`) and its notifications (unique per person,
message and reason) and adds nothing.
"""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, emit
from app.modules.messaging.models import Message
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.notifications import announce
from app.modules.messaging.repository import readers_of
from app.modules.messaging.thread_repository import PageThreadRepository
from app.modules.proposals.repository import ProposalFacts
from app.modules.wiki.events import PAGE_REVIEW_DUE
from app.modules.wiki.models import Page, PageStatus
from app.worker.registry import handler


async def notify_on_review_due(session: AsyncSession, event: Event) -> None:
    if event.type != PAGE_REVIEW_DUE or event.subject_type != "page":
        return
    threads = PageThreadRepository(session, event.org_id)
    page = await threads.page(event.subject_id)
    if (
        page is None
        or page.trashed_at is not None
        or page.status != PageStatus.PUBLISHED
        or page.review_notified_at is None
    ):
        return
    entry = await _entry(session, threads, event, page)
    if entry is None or entry.conversation_id is None:
        return
    moderators = await ProposalFacts(session, event.org_id).moderators(page.space_id)
    readers = await readers_of(session, event.org_id, entry.conversation_id, moderators)
    rows = [(u, NotificationReason.REVIEW_DUE) for u in sorted(readers)]
    for notification in await NotificationRepository(session, event.org_id).add(entry, rows):
        await announce(session, event, notification)


async def _entry(
    session: AsyncSession, threads: PageThreadRepository, event: Event, page: Page
) -> Message | None:
    """The event's timeline entry, written unless it exists."""
    thread = await threads.thread_for(page)
    body = json.dumps({"key": PAGE_REVIEW_DUE})
    message = await threads.add_system(thread, event.id, body, event.created_at)
    if message is None:
        return await threads.system_message(event.id)
    await emit(
        session,
        type="message.created",
        actor=event.acting,
        space_id=page.space_id,
        subject_type="message",
        subject_id=message.id,
        payload={
            "conversation_id": str(thread.id),
            "message_id": str(message.id),
            "parent_id": None,
            "system": True,
        },
    )
    return message


handler((PAGE_REVIEW_DUE,), "notify_on_review_due")(notify_on_review_due)
