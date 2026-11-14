"""Ticket threads (plan M4 task 3, spec 6.1, 6.2): one conversation per ticket, seen by
whoever sees the ticket; a system timeline written by `ticket_timeline` (one message
per changed field, however often an event is handed over); channels and DMs never get
a word about tickets."""

import json
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.modules.messaging.models import Conversation, ConversationKind, Message
from app.modules.spaces.repository import SpaceRepository
from tests.factories_messaging import post, send
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of
from tests.factories_wiki import new_page, publish
from tests.page_thread_helpers import keys, messages, thread_of, timeline
from tests.ticket_thread_helpers import message_handlers, ticket_handlers, ticket_thread


def _ref(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


async def test_one_thread_per_ticket_for_whoever_sees_it(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    thread = await ticket_thread(desk.viewer, ticket)
    assert (thread["kind"], thread["space_id"], thread["name"]) == (
        "thread_ticket",
        desk.space_id,
        None,
    )
    assert (await ticket_thread(desk.admin, ticket))["id"] == thread["id"]
    hidden = await desk.outsider.get(f"/api/tickets/{ticket['number']}/thread")
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "ticket.not_found"
    unseen = await desk.outsider.get(f"/api/conversations/{thread['id']}/messages")
    assert unseen.json()["error"]["code"] == "conversation.not_found"
    comment = await post(desk.viewer, thread["id"], "Ein Kommentar")  # channel.post: viewer
    assert comment["kind"] == "human"
    assert (await send(desk.outsider, thread["id"], "Nein")).status_code == 404


async def test_every_change_is_one_system_message_however_often_delivered(
    desk: Desk, session: AsyncSession
) -> None:
    epic = await new_ticket(desk.editor, desk.space_id, "Epos", kind="epic")
    ticket = await new_ticket(desk.moderator, desk.space_id, "Alt", assignee=_ref(desk, "editor"))
    active = await status_of(desk.viewer, desk.space_id, "active")
    r = await patch(
        desk.moderator,
        ticket,
        title="Neu",
        description_md="Beschreibung",
        status_id=active["id"],
        priority="urgent",
        kind="story",
        parent_id=epic["id"],
        due_on="2027-01-15",
        assignee=_ref(desk, "editor2"),
    )
    assert r.status_code == 200, r.text
    r = await patch(desk.editor2, r.json(), assignee=None)
    for _ in range(2):
        await ticket_handlers(session)
    await ticket_handlers(session, notify_first=True)
    thread = await ticket_thread(desk.viewer, ticket)
    items = await messages(desk.viewer, thread["id"])
    assert keys(items) == [
        "ticket.created",
        "ticket.assigned",
        "ticket.status_changed",
        "ticket.assigned",
        "ticket.priority_changed",
        "ticket.kind_changed",
        "ticket.parent_changed",
        "ticket.due_changed",
        "ticket.title_changed",
        "ticket.description_changed",
        "ticket.unassigned",
    ]
    entries = [m["system"] for m in items]
    moderator = {"id": desk.id_of("moderator"), "name": "Desk moderator", "type": "user"}
    assert entries[0] == {
        "key": "ticket.created",
        "actor": moderator,
        "number": None,
        "old": None,
        "new": None,
        "run_id": None,
        "automation_id": None,
        "budget_scope": None,
    }
    assert entries[1]["new"] == {"value": desk.id_of("editor"), "name": "Desk editor"}
    assert entries[2]["old"] == {"value": ticket["status"]["id"], "name": "Neu"}
    assert entries[2]["new"] == {"value": active["id"], "name": "In Arbeit"}
    assert entries[3]["old"]["name"] == "Desk editor"
    assert entries[3]["new"]["name"] == "Desk editor2"
    assert entries[4]["old"] == {"value": "normal", "name": None}
    assert entries[4]["new"] == {"value": "urgent", "name": None}
    assert entries[6]["old"] is None
    assert entries[6]["new"] == {"value": epic["id"], "name": epic["key"]}
    assert entries[7]["new"] == {"value": "2027-01-15", "name": None}
    assert entries[8]["old"] is entries[8]["new"] is None  # no titles in the timeline
    assert entries[10]["old"]["name"] == "Desk editor2"
    assert all("Alt" not in m["body_md"] and "Neu" not in m["body_md"] for m in items)
    hidden = await messages(desk.viewer, thread["id"], include_system="false")
    assert hidden == []


async def test_no_way_writes_about_tickets_into_channels_or_dms(
    desk: Desk, session: AsyncSession
) -> None:
    channel = await desk.manager.post(
        f"/api/spaces/{desk.space_id}/channels", json={"name": "team"}
    )
    dm = await desk.editor.post("/api/dms", json={"user_ids": [desk.id_of("moderator")]})
    assert channel.status_code == 201 and dm.status_code in (200, 201)
    before = await session.scalar(select(func.count()).select_from(Message))
    ticket = await new_ticket(desk.editor, desk.space_id, assignee=_ref(desk, "editor"))
    done = await status_of(desk.viewer, desk.space_id, "done")
    for status in (done["id"], ticket["status"]["id"]):
        ticket = (await patch(desk.editor, ticket, status_id=status)).json()
    await ticket_handlers(session)
    await message_handlers(session)
    kinds = await session.execute(
        select(Conversation.kind, func.count())
        .join(Message, Message.conversation_id == Conversation.id)
        .group_by(Conversation.kind)
    )
    by_kind = dict(kinds.all())
    assert set(by_kind) == {ConversationKind.THREAD_TICKET}
    assert by_kind[ConversationKind.THREAD_TICKET] == await session.scalar(
        select(func.count()).select_from(Message)
    ) - (before or 0)


async def test_the_database_takes_system_messages_in_ticket_threads_only(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    thread = await ticket_thread(desk.viewer, ticket)
    await session.execute(
        text(
            "INSERT INTO message (id, org_id, conversation_id, author_type, kind, body_md,"
            " client_id, created_at, reply_count)"
            " SELECT gen_random_uuid(), org_id, id, 'system', 'system', '{}',"
            " gen_random_uuid(), now(), 0 FROM conversation WHERE id = :id"
        ),
        {"id": thread["id"]},
    )
    kind = await session.scalar(select(Conversation.kind).where(Conversation.id == thread["id"]))
    assert kind == "thread_ticket"


async def test_nobody_replies_to_a_system_message(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    page = await publish(desk.editor, await new_page(desk.editor, desk.space_id, "Seite"))
    await ticket_handlers(session)
    await timeline(session)
    for thread in (await ticket_thread(desk.viewer, ticket), await thread_of(desk.viewer, page)):
        (system,) = [m for m in await messages(desk.viewer, thread["id"]) if m["kind"] == "system"][
            :1
        ]
        r = await send(desk.viewer, thread["id"], "Antwort", parent_id=system["id"])
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "message.bad_parent"


async def test_losing_the_space_loses_the_thread(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    thread = await ticket_thread(desk.editor2, ticket)
    await post(desk.editor2, thread["id"], "Noch da")
    await SpaceRepository(session).remove_member(
        desk.space.id, Principal.user(desk.users["editor2"].id)
    )
    for path in (
        f"/api/tickets/{ticket['number']}/thread",
        f"/api/conversations/{thread['id']}",
        f"/api/conversations/{thread['id']}/messages",
    ):
        assert (await desk.editor2.get(path)).status_code == 404, path


async def test_activity_and_search_lead_to_the_ticket(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, "Drucker")
    thread = await ticket_thread(desk.viewer, ticket)
    body = {
        "body_md": "@Desk editor Tonerkartusche getauscht",
        "mentions": [desk.id_of("editor")],
    }
    sent = await desk.viewer.post(f"/api/conversations/{thread['id']}/messages", json=body)
    assert sent.status_code == 201, sent.text
    await message_handlers(session)
    (entry,) = (await desk.editor.get("/api/activity")).json()["items"]
    assert entry["conversation"] == {
        "id": thread["id"],
        "kind": "thread_ticket",
        "name": None,
        "space_id": desk.space_id,
        "page_id": None,
        "ticket_number": ticket["number"],
    }
    found = await desk.viewer.get("/api/search", params={"q": "Tonerkartusche", "types": "message"})
    assert found.status_code == 200, found.text
    (hit,) = found.json()["items"]
    assert hit["conversation"]["ticket_number"] == ticket["number"]
    assert hit["conversation"]["kind"] == "thread_ticket"
    nothing = await desk.outsider.get("/api/search", params={"q": "Tonerkartusche"})
    assert nothing.json()["items"] == []


async def _body(session: AsyncSession, items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """The stored body of the entry with `key` (the API shows only `system`)."""
    entry = next(m for m in items if m["system"] and m["system"]["key"] == key)
    assert entry["body_md"] == ""
    body: dict[str, Any] = json.loads(
        await session.scalar(select(Message.body_md).where(Message.id == entry["id"])) or ""
    )
    return body


async def test_a_deleted_status_moves_tickets_with_a_timeline_entry(
    desk: Desk, session: AsyncSession
) -> None:
    review = await status_of(desk.viewer, desk.space_id, "review")
    active = await status_of(desk.viewer, desk.space_id, "active")
    ticket = await new_ticket(desk.editor, desk.space_id, status_id=review["id"])
    r = await desk.manager.delete(
        f"/api/ticket-statuses/{review['id']}",
        params={"version": review["version"], "replace_with": active["id"]},
    )
    assert r.status_code == 204
    await ticket_handlers(session)
    items = await messages(desk.viewer, (await ticket_thread(desk.viewer, ticket))["id"])
    body = await _body(session, items, "ticket.status_changed")
    assert (body["from"], body["to"]) == (review["id"], active["id"])
    entry = next(m["system"] for m in items if m["system"]["key"] == "ticket.status_changed")
    assert entry["old"] is None  # the status is gone: neither name nor id


async def test_an_entry_names_no_ticket_or_status_its_reader_cannot_see(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    """Review M4 P1: whatever ids an entry was written with, a reader sees a parent's key
    or a status's name only where it may see that space, and never the raw id."""
    secret = await make_space("team", "Geheim", members=[(desk.users["editor"], "editor")])
    hidden = await new_ticket(desk.editor, secret.id, "Versteckt")
    ticket = await new_ticket(desk.editor, desk.space_id)
    thread = await ticket_thread(desk.viewer, ticket)
    for key, ref in (
        ("ticket.parent_changed", hidden["id"]),
        ("ticket.status_changed", hidden["status"]["id"]),
    ):
        body = {"key": key, "actor": desk.id_of("editor"), "from": None, "to": ref}
        await session.execute(
            text(
                "INSERT INTO message (id, org_id, conversation_id, author_type, kind, body_md,"
                " client_id, created_at, reply_count)"
                " SELECT gen_random_uuid(), org_id, id, 'system', 'system', :body,"
                " gen_random_uuid(), now(), 0 FROM conversation WHERE id = :id"
            ),
            {"id": thread["id"], "body": json.dumps(body)},
        )
    listed = await desk.viewer.get(f"/api/conversations/{thread['id']}/messages")
    assert listed.status_code == 200, listed.text
    assert hidden["id"] not in listed.text and hidden["status"]["id"] not in listed.text
    entries = {m["system"]["key"]: m["system"] for m in listed.json()["items"] if m["system"]}
    assert entries["ticket.parent_changed"]["new"] is None
    assert entries["ticket.status_changed"]["new"] is None
    seen = await desk.editor.get(f"/api/conversations/{thread['id']}/messages")
    named = {m["system"]["key"]: m["system"] for m in seen.json()["items"] if m["system"]}
    assert named["ticket.parent_changed"]["new"] == {
        "value": hidden["id"],
        "name": f"HC-{hidden['number']}",
    }
