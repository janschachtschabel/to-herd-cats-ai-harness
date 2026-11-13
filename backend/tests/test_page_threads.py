"""Page threads and their system timeline (plan M3 task 8, spec 6.1, 6.2; review focus
2 and 7).

A page's thread is seen by whoever sees the page: drafts only with `page.edit`, and
nothing while the page is in the trash; purging a page removes its thread with
everything attached. The system timeline itself: `test_page_timeline.py`.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.notifications import notify_on_message
from app.modules.messaging.social_models import ConversationRead, MessageMention, Reaction
from app.modules.wiki.events import PAGE_EVENTS
from tests.factories_wiki import Wiki, new_page, publish
from tests.page_thread_helpers import events_of, messages, thread_of, timeline


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
        "ticket_number": None,
    }
    assert (await wiki.viewer.get("/api/activity")).json()["items"] == []


async def test_an_import_emits_nothing_and_its_pages_get_threads_when_opened(
    wiki: Wiki, session: AsyncSession
) -> None:
    from tests.test_wiki_import_export import _import, _zip

    imported = await _import(wiki.admin, wiki.space_id, _zip({"a.md": "A", "b.md": "B"}))
    assert imported.status_code == 200, imported.text
    assert await events_of(session, *PAGE_EVENTS, "space.imported") == []
    tree = await wiki.viewer.get(f"/api/spaces/{wiki.space_id}/pages/tree")
    page = tree.json()["items"][0]
    thread = await thread_of(wiki.viewer, page)
    assert await messages(wiki.viewer, thread["id"]) == []
