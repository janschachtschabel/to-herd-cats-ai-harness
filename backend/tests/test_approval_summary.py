"""Module review M8 5, L1: an approval's summary names only what the system resolved
(a ticket's key once the run found the ticket where it answers, a status as its
space's status is named, an id of an object the release is bound to), never a string
the model chose; it is the asked person's alone (`GET /api/approvals/{id}`: null for
everyone else). The card in the conversation says only the tool's name, and in a
marked run's DM alone with her it is marked personal. With or without the mark."""

from typing import Any

from sqlalchemy import select

from app.modules.messaging.models import Message
from tests.factories_external import Ext, call
from tests.factories_personal import pending
from tests.factories_tickets import status_of
from tests.factories_writing import Work
from tests.test_approvals import confirm
from tests.test_personal_mark_readers import INSPECT
from tests.test_personal_release_confirm import _confirm
from tests.test_run_external_personal import SECRET, _channel, _personal


async def _replies(client: Any, root: str) -> list[dict[str, Any]]:
    r = await client.get(f"/api/messages/{root}/replies?limit=100")
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


async def _mention(ext: Ext, channel: str) -> str:
    body = {"body_md": "@Ava such meine Issues", "mentions": [str(ext.bench.agent.id)]}
    r = await ext.bench.people.alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert r.status_code == 201, r.text
    await ext.bench.run_next()
    return str(r.json()["id"])


async def test_a_card_in_a_channel_never_shows_what_she_read(ext: Ext, work: Work) -> None:
    """Under the mark, `set_ticket_status` with a status that is none of the space's:
    the card where everyone in the channel reads holds none of it."""
    channel = await _channel(work)
    ticket = await work.ticket()
    name = await _personal(ext)
    await _confirm(ext, "set_ticket_status", name)
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="meine"),  # her own connector: the run is marked
            call("set_ticket_status", key=ticket["key"], status=f"Fund {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    root = await _mention(ext, channel)
    found = [e for e in await ext.tool_events() if e["name"] == name]
    assert found and found[-1]["read"]["personal"] is True  # marked
    seen = [m["body_md"] for m in await _replies(work.admin, root)]
    assert "set_ticket_status" in seen  # the card: the tool's name only
    in_channel = await ext.bench.session.scalars(
        select(Message.body_md).where(Message.conversation_id == channel)
    )
    assert not any(SECRET in b for b in seen), seen
    assert not any(SECRET in b for b in in_channel)
    (approval,) = await pending(ext.bench.people.alice)
    assert approval["summary"] == f"set_ticket_status: key={ticket['key']}"  # no status


async def test_a_read_tools_card_in_a_channel_never_shows_what_she_read(
    ext: Ext, work: Work
) -> None:
    """`read_ticket` on `confirm` with a key that names no ticket: not in the card,
    not in the summary."""
    channel = await _channel(work)
    name = await _personal(ext)
    await _confirm(ext, "read_ticket", name)
    ext.bench.stub.state.replies.extend(
        [call(name, q="meine"), call("read_ticket", key=SECRET), {"content": "Erledigt."}]
    )
    root = await _mention(ext, channel)
    seen = [m["body_md"] for m in await _replies(work.admin, root)]
    assert not any(SECRET in b for b in seen), seen
    (approval,) = await pending(ext.bench.people.alice)
    assert approval["summary"] == "read_ticket"


async def test_without_the_mark_a_free_text_never_reaches_the_card(work: Work) -> None:
    await confirm(work, "read_ticket")
    work.bench.stub.state.replies.extend(
        [call("read_ticket", key="Geheim-4711"), {"content": "Erledigt."}]
    )
    await work.bench.say("Lies das Ticket")
    assert await work.bench.run_next() is None  # waits
    (approval,) = await pending(work.bench.people.alice)
    assert approval["summary"] == "read_ticket"
    (card,) = [m for m in await work.bench.messages() if m["kind"] == "approval"]
    assert card["body_md"] == "read_ticket" and card["personal"] is False


async def test_a_summary_names_the_key_and_the_status_as_the_system_has_them(
    work: Work,
) -> None:
    ticket = await work.ticket()
    review = await status_of(work.admin, work.space.id, "review")
    await confirm(work, "set_ticket_status")
    number = str(ticket["number"])  # a bare number names the ticket too
    status = str(review["name"]).upper()
    work.bench.stub.state.replies.extend(
        [call("set_ticket_status", key=number, status=status), {"content": "Erledigt."}]
    )
    await work.bench.say("Bitte zur Prüfung")
    assert await work.bench.run_next() is None  # waits
    (approval,) = await pending(work.bench.people.alice)
    expected = f"set_ticket_status: key={ticket['key']}, status={review['name']}"
    assert approval["summary"] == expected


async def test_only_the_person_asked_reads_the_summary(work: Work) -> None:
    ticket = await work.ticket()
    await confirm(work, "read_ticket")
    work.bench.stub.state.replies.extend(
        [call("read_ticket", key=ticket["key"]), {"content": "Erledigt."}]
    )
    await work.bench.say("Lies das Ticket")
    assert await work.bench.run_next() is None  # waits
    (approval,) = await pending(work.bench.people.alice)
    assert approval["summary"] == f"read_ticket: key={ticket['key']}"
    theirs = await work.admin.get(f"/api/approvals/{approval['id']}")
    assert theirs.status_code == 200, theirs.text
    assert (theirs.json()["summary"], theirs.json()["redacted"]) == (None, True)
    for who in ("admin", "bob", "carol"):
        r = await getattr(work.bench.people, who).get("/api/activity?limit=100")
        assert r.status_code == 200 and ticket["key"] not in r.text, who


async def test_a_marked_runs_card_in_her_dm_is_personal(ext: Ext, work: Work) -> None:
    """Withheld from an admin's inspection of the DM, like every marked message."""
    ticket = await work.ticket()
    name = await _personal(ext)
    await _confirm(ext, "comment_ticket", name)
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="meine"),
            call("comment_ticket", key=ticket["key"], text=f"Fund {SECRET}"),
            {"content": "Ok."},
        ]
    )
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() is None  # waits for her release
    (card,) = [m for m in await ext.bench.messages() if m["kind"] == "approval"]
    assert card["personal"] is True and card["body_md"] == "comment_ticket"
    people = ext.bench.people
    body = {"conversation_id": ext.bench.dm_id, "reason": "Prüfung nach Hinweis, Fall 12"}
    granted = await people.admin.post(INSPECT, json=body)
    assert granted.status_code == 201, granted.text
    r = await people.admin.get(f"{INSPECT}/{granted.json()['id']}/messages?limit=100")
    assert r.status_code == 200, r.text
    shown = {m["id"]: m for m in r.json()["items"]}
    assert shown[card["id"]]["body_md"] == ""
