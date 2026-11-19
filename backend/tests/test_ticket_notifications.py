"""Notifications about tickets (plan M4 decision 10): `assignment` when someone assigns
me (not when I take a ticket myself), `ticket_comment` for a comment on a ticket I am
assigned to or reported (not my own, not on top of a mention or a reply); only for
people who may see the ticket when the handler runs. Handlers run here in the test's
transaction, as the worker would, more than once where that matters."""

from dataclasses import replace
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.core.principal import Principal
from app.modules.messaging.live_publish import of_event
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.notifications import notify_on_message
from app.modules.spaces.repository import SpaceRepository
from tests.factories_messaging import post
from tests.factories_tickets import Desk, new_ticket, patch
from tests.ticket_thread_helpers import message_handlers, ticket_handlers, ticket_thread


def _ref(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


async def _for_me(client: AsyncClient) -> list[tuple[str, str | None]]:
    """(reason, conversation kind) of every activity entry, newest first."""
    r = await client.get("/api/activity")
    assert r.status_code == 200, r.text
    return [(e["reason"], e["conversation"]["kind"]) for e in r.json()["items"]]


async def _count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Notification)) or 0)


async def test_being_assigned_notifies_once(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    r = await patch(desk.moderator, ticket, assignee=_ref(desk, "editor2"))
    assert r.status_code == 200
    for notify_first in (True, False, False):
        await ticket_handlers(session, notify_first=notify_first)
    assert await _for_me(desk.editor2) == [("assignment", "thread_ticket")]
    (entry,) = (await desk.editor2.get("/api/activity")).json()["items"]
    assert entry["conversation"]["ticket_number"] == ticket["number"]
    # A timeline entry has no author: the activity names who assigned, and shows no
    # snippet (its body is the entry's key and ids, for the client to word).
    assert entry["author"] == {
        "type": "user",
        "id": desk.id_of("moderator"),
        "name": "Desk moderator",
    }
    assert entry["snippet"] == ""
    assert await _count(session) == 1
    created = await session.scalar(
        select(func.count())
        .select_from(EventOutbox)
        .where(EventOutbox.type == "notification.created")
    )
    assert created == 1


async def test_created_with_an_assignee_notifies_too(desk: Desk, session: AsyncSession) -> None:
    await new_ticket(desk.moderator, desk.space_id, assignee=_ref(desk, "viewer"))
    await ticket_handlers(session)
    assert await _for_me(desk.viewer) == [("assignment", "thread_ticket")]


async def test_taking_a_ticket_oneself_notifies_nobody(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, assignee=_ref(desk, "editor"))
    other = await new_ticket(desk.editor, desk.space_id)
    await patch(desk.editor2, other, assignee=_ref(desk, "editor2"))
    released = await patch(desk.editor, ticket, assignee=None)
    assert released.status_code == 200
    await ticket_handlers(session)
    assert await _count(session) == 0


async def test_no_assignment_notification_after_losing_access(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    await patch(desk.moderator, ticket, assignee=_ref(desk, "editor2"))
    await SpaceRepository(session).remove_member(
        desk.space.id, Principal.user(desk.users["editor2"].id)
    )
    await ticket_handlers(session)
    assert await _count(session) == 0


async def test_a_comment_notifies_assignee_and_reporter(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, assignee=_ref(desk, "editor"))
    ticket = (await patch(desk.moderator, ticket, assignee=_ref(desk, "editor2"))).json()
    thread = await ticket_thread(desk.viewer, ticket)
    await ticket_handlers(session)
    await post(desk.viewer, thread["id"], "Ein Hinweis")
    await post(desk.editor2, thread["id"], "Mein eigener")
    for _ in range(2):
        await message_handlers(session)
    assert await _for_me(desk.editor) == [("ticket_comment", "thread_ticket")] * 2  # reporter
    assert await _for_me(desk.editor2) == [
        ("ticket_comment", "thread_ticket"),
        ("assignment", "thread_ticket"),
    ]
    assert await _for_me(desk.viewer) == []
    assert await _for_me(desk.moderator) == []


async def test_a_mention_or_a_reply_is_not_doubled(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    thread = await ticket_thread(desk.viewer, ticket)
    url = f"/api/conversations/{thread['id']}/messages"
    mention = {"body_md": "@editor schau", "mentions": [desk.id_of("editor")]}
    assert (await desk.viewer.post(url, json=mention)).status_code == 201
    top = await post(desk.editor, thread["id"], "Frage")
    await post(desk.viewer, thread["id"], "Antwort", parent_id=top["id"])
    await message_handlers(session)
    assert await _for_me(desk.editor) == [
        ("reply", "thread_ticket"),
        ("mention", "thread_ticket"),
    ]


async def test_no_comment_notification_after_losing_access(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor2, desk.space_id)
    thread = await ticket_thread(desk.viewer, ticket)
    await post(desk.viewer, thread["id"], "Hallo")
    await SpaceRepository(session).remove_member(
        desk.space.id, Principal.user(desk.users["editor2"].id)
    )
    await message_handlers(session)
    assert await _count(session) == 0


async def test_live_events_name_the_thread_and_the_ticket_only(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, "Geheimer Titel")
    await patch(desk.editor, ticket, title="Noch geheimer")
    thread = await ticket_thread(desk.viewer, ticket)
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.like("ticket.%")).order_by(EventOutbox.id)
    )
    lives = [of_event(Event.of(row)) for row in rows.all()]
    assert [live.name for live in lives if live] == ["ticket.created", "ticket.updated"]
    for live in lives:
        assert live is not None
        assert str(live.conversation_id) == thread["id"]
        assert str(live.ticket_id) == ticket["id"]
        assert live.user_id is None and live.message_id is None
        frame: Any = live.frame().decode()
        assert "geheim" not in frame.lower()
        assert f'"ticket_id":"{ticket["id"]}"' in frame


async def test_timeline_entries_are_flagged_and_never_loaded_for_notifications(
    desk: Desk, session: AsyncSession
) -> None:
    """Review M4 P3: a timeline entry's `message.created` says it is a system message,
    so `notify_on_message` returns at once (no query) instead of loading it."""
    ticket = await new_ticket(desk.editor, desk.space_id)
    await patch(desk.moderator, ticket, assignee=_ref(desk, "editor2"))
    await ticket_handlers(session)
    thread = await ticket_thread(desk.viewer, ticket)
    rows = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == "message.created"))
    ).all()
    entries = [r for r in rows if r.payload["conversation_id"] == thread["id"]]
    assert len(entries) == 2 and all(r.payload["system"] is True for r in entries)
    # Even an event pointing at a human message with a mention is skipped if flagged.
    r = await desk.editor.post(
        f"/api/conversations/{thread['id']}/messages",
        json={"body_md": "Hallo @viewer", "mentions": [desk.id_of("viewer")]},
    )
    assert r.status_code == 201, r.text
    human = r.json()
    (row,) = (
        await session.scalars(
            select(EventOutbox).where(
                EventOutbox.type == "message.created", EventOutbox.subject_id == human["id"]
            )
        )
    ).all()
    before = await _count(session)
    flagged = Event.of(row)
    await notify_on_message(session, replace(flagged, payload={**flagged.payload, "system": True}))
    assert await _count(session) == before
    await notify_on_message(session, flagged)
    assert await _count(session) > before
