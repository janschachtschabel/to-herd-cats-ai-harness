"""Page threads and their system timeline (plan M3 task 8, spec 6.1, 6.2; review focus
2 and 7).

A page's thread is seen by whoever sees the page: drafts only with `page.edit`, and
nothing while the page is in the trash. The wiki emits its events in the changing
transaction; the handler `page_timeline` (run here in the test's transaction, as the
worker would, and more than once where that matters) writes one system message per
event: a key and parameters, never text. System messages notify nobody, and purging a
page removes its thread with everything attached.
"""

import json
import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.notifications import notify_on_message
from app.modules.messaging.social_models import ConversationRead, MessageMention, Reaction
from app.modules.messaging.threads import page_timeline
from app.modules.wiki.events import PAGE_EVENTS
from tests.factories_wiki import Wiki, new_page, publish


async def timeline(session: AsyncSession) -> None:
    """Hand every wiki event so far to the handler (again, if it had them)."""
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.in_(PAGE_EVENTS)).order_by(EventOutbox.id)
    )
    for row in rows.all():
        await page_timeline(session, Event.of(row))


async def thread_of(client: AsyncClient, page: dict[str, Any]) -> dict[str, Any]:
    response = await client.get(f"/api/pages/{page['id']}/thread")
    assert response.status_code == 200, response.text
    thread: dict[str, Any] = response.json()
    return thread


async def messages(client: AsyncClient, conversation_id: str, **params: Any) -> list[Any]:
    response = await client.get(f"/api/conversations/{conversation_id}/messages", params=params)
    assert response.status_code == 200, response.text
    return list(reversed(response.json()["items"]))  # oldest first


def keys(items: list[dict[str, Any]]) -> list[str]:
    return [json.loads(m["body_md"])["key"] for m in items if m["kind"] == "system"]


async def _events(session: AsyncSession, *types: str) -> list[str]:
    rows = await session.scalars(
        select(EventOutbox.type).where(EventOutbox.type.in_(types)).order_by(EventOutbox.id)
    )
    return list(rows)


async def test_the_thread_follows_the_page_draft_included(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    thread = await thread_of(wiki.editor, page)
    assert (thread["kind"], thread["page_id"], thread["space_id"]) == (
        "thread_page",
        page["id"],
        wiki.space_id,
    )
    assert thread["can_post"] is True
    assert (await thread_of(wiki.editor2, page))["id"] == thread["id"]  # one per page
    for name in ("viewer", "outsider"):
        response = await wiki.clients[name].get(f"/api/pages/{page['id']}/thread")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "page.not_found"
        response = await wiki.clients[name].get(f"/api/conversations/{thread['id']}")
        assert response.json()["error"]["code"] == "conversation.not_found"
    await publish(wiki.editor, page)
    assert (await thread_of(wiki.viewer, page))["id"] == thread["id"]
    response = await wiki.outsider.get(f"/api/conversations/{thread['id']}/messages")
    assert response.status_code == 404


async def test_readers_may_comment_on_a_published_page(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    thread = await thread_of(wiki.viewer, page)
    sent = await wiki.viewer.post(
        f"/api/conversations/{thread['id']}/messages", json={"body_md": "Frage"}
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["kind"] == "human"


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
    assert (await _events(session, "page.published")).count("page.published") == 2


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


async def test_a_trashed_page_hides_its_thread(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    thread = await thread_of(wiki.viewer, page)
    sent = await wiki.viewer.post(
        f"/api/conversations/{thread['id']}/messages", json={"body_md": "Hallo"}
    )
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert trashed.status_code == 204
    for client in (wiki.viewer, wiki.editor, wiki.moderator):
        assert (await client.get(f"/api/pages/{page['id']}/thread")).status_code == 404
        assert (await client.get(f"/api/conversations/{thread['id']}")).status_code == 404
        reply = await client.get(f"/api/messages/{sent.json()['id']}/replies")
        assert reply.json()["error"]["code"] == "message.not_found"
    assert (await wiki.moderator.post(f"/api/pages/{page['id']}/restore")).status_code == 200
    assert (await thread_of(wiki.viewer, page))["id"] == thread["id"]


async def test_purge_removes_the_thread_with_everything_attached(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    child = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=page["id"])
    )
    threads = [await thread_of(wiki.viewer, p) for p in (page, child)]
    sent = await wiki.viewer.post(
        f"/api/conversations/{threads[0]['id']}/messages",
        json={"body_md": "@editor", "mentions": [str(wiki.users["editor"].id)]},
    )
    message_id = sent.json()["id"]
    await wiki.editor.put(f"/api/messages/{message_id}/reactions/%F0%9F%91%8D")
    await wiki.editor.post(
        f"/api/conversations/{threads[0]['id']}/read", json={"message_id": message_id}
    )
    for row in (await session.scalars(select(EventOutbox))).all():
        if row.type == "message.created":
            await notify_on_message(session, Event.of(row))
    await timeline(session)
    assert await session.scalar(select(func.count()).select_from(Notification)) == 1
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert trashed.status_code == 204
    assert (await wiki.admin.delete(f"/api/pages/{page['id']}")).status_code == 204
    ids = [uuid.UUID(t["id"]) for t in threads]
    for model, column in (
        (Conversation, Conversation.id.in_(ids)),
        (Message, Message.conversation_id.in_(ids)),
        (MessageMention, MessageMention.message_id == uuid.UUID(message_id)),
        (Reaction, Reaction.message_id == uuid.UUID(message_id)),
        (ConversationRead, ConversationRead.conversation_id.in_(ids)),
        (Notification, Notification.conversation_id.in_(ids)),
    ):
        count = await session.scalar(select(func.count()).select_from(model).where(column))
        assert count == 0, model
    await timeline(session)  # a late event of the purged page creates nothing again
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.page_id.in_([uuid.UUID(page["id"]), uuid.UUID(child["id"])]))
        )
        == 0
    )


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


async def test_system_messages_are_not_unread_and_threads_wait_until_opened(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    await timeline(session)
    thread = await thread_of(wiki.viewer, page)
    first = await wiki.editor.post(
        f"/api/conversations/{thread['id']}/messages", json={"body_md": "Eins"}
    )
    unread = (await wiki.viewer.get("/api/conversations/unread")).json()["items"]
    assert unread == []  # a page discussion the viewer never opened does not count
    await wiki.viewer.post(
        f"/api/conversations/{thread['id']}/read", json={"message_id": first.json()["id"]}
    )
    await wiki.editor.post(f"/api/conversations/{thread['id']}/messages", json={"body_md": "Zwei"})
    await wiki.editor.post(
        f"/api/pages/{page['id']}/move",
        json={"parent_id": None, "position": 0, "version": page["version"]},
    )
    await timeline(session)
    unread = (await wiki.viewer.get("/api/conversations/unread")).json()["items"]
    assert unread == [{"conversation_id": thread["id"], "unread": 1, "mentions": 0}]


async def test_mentions_in_a_page_thread_lead_to_the_page(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    thread = await thread_of(wiki.editor, page)
    sent = await wiki.editor.post(
        f"/api/conversations/{thread['id']}/messages",
        json={
            "body_md": "@viewer @editor2",
            "mentions": [str(wiki.users["viewer"].id), str(wiki.users["editor2"].id)],
        },
    )
    assert sent.json()["not_notified"] == [str(wiki.users["viewer"].id)]  # a draft
    for row in (await session.scalars(select(EventOutbox))).all():
        if row.type == "message.created":
            await notify_on_message(session, Event.of(row))
    (entry,) = (await wiki.editor2.get("/api/activity")).json()["items"]
    assert entry["conversation"] == {
        "id": thread["id"],
        "kind": "thread_page",
        "name": None,
        "space_id": wiki.space_id,
        "page_id": page["id"],
    }
    assert (await wiki.viewer.get("/api/activity")).json()["items"] == []


async def test_system_messages_stay_on_the_timeline(wiki: Wiki, session: AsyncSession) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    await timeline(session)
    thread = await thread_of(wiki.moderator, page)
    system = (await messages(wiki.moderator, thread["id"]))[0]
    deleted = await wiki.moderator.delete(f"/api/messages/{system['id']}")
    assert (deleted.status_code, deleted.json()["error"]["code"]) == (403, "message.system")
    edited = await wiki.moderator.patch(f"/api/messages/{system['id']}", json={"body_md": "x"})
    assert edited.status_code == 403


async def test_an_import_emits_once_and_its_pages_get_threads_when_opened(
    wiki: Wiki, session: AsyncSession
) -> None:
    from tests.test_wiki_import_export import _import, _zip

    imported = await _import(wiki.admin, wiki.space_id, _zip({"a.md": "A", "b.md": "B"}))
    assert imported.status_code == 200, imported.text
    assert await _events(session, *PAGE_EVENTS, "space.imported") == ["space.imported"]
    tree = await wiki.viewer.get(f"/api/spaces/{wiki.space_id}/pages/tree")
    page = tree.json()["items"][0]
    thread = await thread_of(wiki.viewer, page)
    assert await messages(wiki.viewer, thread["id"]) == []
