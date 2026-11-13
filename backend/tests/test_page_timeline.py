"""The system timeline of page threads (plan M3 task 8, spec 6.1, 6.2; review focus 2
and 7): the wiki emits its events in the changing transaction; the handler
`page_timeline` (run here in the test's transaction, as the worker would, and more than
once where that matters) writes one system message per event: a key and parameters,
never text, in the order the changes happened. System messages notify nobody and stay.
"""

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.models import Message
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.notifications import notify_on_message
from app.modules.messaging.threads import page_timeline
from app.modules.wiki.events import PAGE_EVENTS
from tests.factories_wiki import Wiki, new_page, publish
from tests.page_thread_helpers import events_of, keys, messages, thread_of, timeline


async def test_publishing_writes_one_system_message_even_when_delivered_twice(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    await publish(wiki.editor, page)
    for _ in range(2):
        await timeline(session)
    thread = await thread_of(wiki.viewer, page)
    items = await messages(wiki.viewer, thread["id"])
    assert keys(items) == ["page.created", "page.published"]
    system = items[1]
    assert system["author"] is None and system["kind"] == "system"
    assert json.loads(system["body_md"]) == {
        "key": "page.published",
        "actor": str(wiki.users["editor"].id),
    }
    editor = wiki.users["editor"]
    assert system["system"] == {
        "key": "page.published",
        "actor": {"id": str(editor.id), "name": editor.name},
        "number": None,
        "old": None,
        "new": None,
    }
    hidden = await messages(wiki.viewer, thread["id"], include_system="false")
    assert hidden == []


async def test_every_page_change_with_a_timeline_entry_emits_its_event(
    wiki: Wiki, session: AsyncSession
) -> None:
    parent = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Oben"))
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    moved = await wiki.editor.post(
        f"/api/pages/{page['id']}/move",
        json={"parent_id": parent["id"], "version": page["version"]},
    )
    assert moved.status_code == 200, moved.text
    edited = await wiki.editor.patch(
        f"/api/pages/{page['id']}",
        json={"content_md": "neu", "version": moved.json()["version"]},
    )
    assert edited.status_code == 200, edited.text  # content changes are not on the timeline
    restored = await wiki.editor.post(
        f"/api/pages/{page['id']}/versions/1/restore", json={"version": edited.json()["version"]}
    )
    assert restored.status_code == 200, restored.text
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": restored.json()["version"]}
    )
    assert trashed.status_code == 204, trashed.text
    back = await wiki.moderator.post(f"/api/pages/{page['id']}/restore")
    assert back.status_code == 200, back.text
    await timeline(session)
    items = await messages(wiki.viewer, (await thread_of(wiki.viewer, page))["id"])
    assert keys(items) == [
        "page.created",
        "page.published",
        "page.moved",
        "page.version_restored",
        "page.trashed",
        "page.restored",
    ]
    restore = next(m for m in items if "version_restored" in m["body_md"])
    assert json.loads(restore["body_md"])["number"] == 1
    assert restore["system"]["number"] == 1
    refused = await wiki.editor.post(f"/api/pages/{parent['id']}/publish", json={"version": 99})
    assert refused.status_code == 409  # a refused change emits nothing
    assert (await events_of(session, "page.published")).count("page.published") == 2


async def test_a_system_message_notifies_nobody(wiki: Wiki, session: AsyncSession) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    await timeline(session)
    rows = await session.scalars(select(EventOutbox).where(EventOutbox.type == "message.created"))
    created = rows.all()
    assert len(created) == 2  # one per system message, for live delivery
    for row in created:
        await notify_on_message(session, Event.of(row))
    assert await session.scalar(select(func.count()).select_from(Notification)) == 0
    assert page["id"]


async def test_the_timeline_never_writes_outside_a_page_thread(
    wiki: Wiki, session: AsyncSession
) -> None:
    """Review focus 7: an event whose subject is not a page (a channel's id, say)
    finds no page and writes nothing."""
    channel = await wiki.moderator.post(f"/api/spaces/{wiki.space_id}/channels", json={"name": "k"})
    channel_id = uuid.UUID(channel.json()["id"])
    row = (await session.scalars(select(EventOutbox).limit(1))).one()
    forged = Event.of(row)
    for type_ in PAGE_EVENTS:
        await page_timeline(
            session,
            Event(
                id=uuid.uuid4(),
                org_id=forged.org_id,
                type=type_,
                actor=forged.actor,
                space_id=wiki.space.id,
                subject_type="page",
                subject_id=channel_id,
                payload={"page_id": str(channel_id)},
                created_at=forged.created_at,
            ),
        )
    count = await session.scalar(
        select(func.count()).select_from(Message).where(Message.kind == "system")
    )
    assert count == 0


async def test_system_messages_stay_on_the_timeline(wiki: Wiki, session: AsyncSession) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    await timeline(session)
    thread = await thread_of(wiki.moderator, page)
    system = (await messages(wiki.moderator, thread["id"]))[0]
    deleted = await wiki.moderator.delete(f"/api/messages/{system['id']}")
    assert (deleted.status_code, deleted.json()["error"]["code"]) == (403, "message.system")
    edited = await wiki.moderator.patch(f"/api/messages/{system['id']}", json={"body_md": "x"})
    assert edited.status_code == 403


async def test_the_timeline_follows_the_changes_not_the_handler(
    wiki: Wiki, session: AsyncSession
) -> None:
    """Review M3 N12: a retry or a second worker may handle a later event first; the
    entries still stand in the order the changes happened, also around a comment
    written in between."""
    page = await new_page(wiki.editor, wiki.space_id, "Seite")
    thread = await thread_of(wiki.editor, page)  # a draft: the editor sees it
    comment = await wiki.editor.post(
        f"/api/conversations/{thread['id']}/messages", json={"body_md": "Zwischendurch"}
    )
    assert comment.status_code == 201
    await publish(wiki.editor, page)
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.in_(PAGE_EVENTS)).order_by(EventOutbox.id)
    )
    for row in reversed(rows.all()):  # published handled before created
        await page_timeline(session, Event.of(row))
    items = await messages(wiki.viewer, thread["id"])
    assert [m["body_md"] if m["kind"] == "human" else keys([m])[0] for m in items] == [
        "page.created",
        "Zwischendurch",
        "page.published",
    ]
    assert items[0]["created_at"] < items[1]["created_at"] < items[2]["created_at"]
