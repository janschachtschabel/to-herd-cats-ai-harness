"""The demo data (scripts/demo_seed.py): people, a team space with pages, channels with
messages, thread replies, mentions and reactions, a direct message, a page discussion
that starts with the worker's system entries, and tickets (scripts/demo_tickets.py; the
sprints in test_demo_sprints).

The script talks to the public API as the browser does; here to the test app. The
worker's handlers run in the test's transaction (`settle`), as in test_page_threads.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.notifications import notify_on_message
from app.modules.messaging.threads import page_timeline
from app.modules.tickets.events import TICKET_EVENTS
from app.modules.tickets.handlers import notify_on_ticket, ticket_timeline
from app.modules.users.models import User
from app.modules.wiki.events import PAGE_EVENTS
from scripts.demo_seed import DemoExists, DemoFailed, main, seed
from tests.factories import PASSWORD, login

DEMO_PASSWORD = "seed-people-pw-123"  # no context word ("demo" of demo.example)


async def _handle(session: AsyncSession, *, tickets: bool = True) -> None:
    """What the worker would do with the events so far (again, where it already did);
    without `tickets`, a worker that knows no ticket handlers."""
    rows = await session.scalars(select(EventOutbox).order_by(EventOutbox.id))
    for row in rows.all():
        if row.type in PAGE_EVENTS:
            await page_timeline(session, Event.of(row))
        elif row.type in TICKET_EVENTS and tickets:
            await ticket_timeline(session, Event.of(row))
            await notify_on_ticket(session, Event.of(row))
        elif row.type == "message.created":
            await notify_on_message(session, Event.of(row))


async def _get(client: AsyncClient, path: str, **params: Any) -> Any:
    response = await client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def _top(client: AsyncClient, conversation_id: str) -> list[dict[str, Any]]:
    page = await _get(client, f"/api/conversations/{conversation_id}/messages", limit=100)
    return list(reversed(page["items"]))  # oldest first


@pytest.fixture
async def demo(
    session: AsyncSession,
    make_client: Callable[..., Awaitable[AsyncClient]],
    owner_user: User,
) -> dict[str, Any]:
    async def connect() -> AsyncClient:
        return await make_client(csrf=True)

    seeded = await seed(
        connect,
        admin_email=owner_user.email,
        admin_password=PASSWORD,
        people_password=DEMO_PASSWORD,
        settle=lambda: _handle(session),
        wait_seconds=0,
    )
    await _handle(session)
    clients = {}
    for key, email in seeded.emails.items():
        clients[key] = await make_client(csrf=True)
        await login(clients[key], email, DEMO_PASSWORD)
    return {"seeded": seeded, "clients": clients, "connect": connect, "owner": owner_user}


async def test_channels_hold_messages_threads_mentions_and_reactions(demo: dict[str, Any]) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    channels = await _get(clara, f"/api/spaces/{seeded.space_id}/channels")
    assert [c["name"] for c in channels["items"]] == ["projekt-kranich", "team-nord"]
    by_name = {c["name"]: c["id"] for c in channels["items"]}

    team = await _top(clara, by_name["team-nord"])
    assert [m["author"]["name"] for m in team] == ["Anna Nord", "Ben Berg"]
    reactions = {r["emoji"]: r["count"] for r in team[0]["reactions"]}
    assert reactions == {"👍": 1, "🎉": 1}
    assert team[1]["mentions"] == [str(seeded.ids["clara"])]

    kranich = await _top(clara, by_name["projekt-kranich"])
    assert kranich[0]["mentions"] == [str(seeded.ids["ben"])]
    assert kranich[0]["reply_count"] == 2
    replies = await _get(clara, f"/api/messages/{kranich[0]['id']}/replies")
    assert [m["author"]["name"] for m in replies["items"]] == ["Ben Berg", "Clara Klein"]


async def test_the_mentioned_and_the_thread_starter_have_activity(demo: dict[str, Any]) -> None:
    clients = demo["clients"]
    reasons = {}
    for key in ("anna", "ben", "clara"):
        items = (await _get(clients[key], "/api/activity"))["items"]
        reasons[key] = sorted(entry["reason"] for entry in items)
    # Ben and Clara were mentioned in channels, Anna in the page discussion. Anna
    # started the Kranich thread (replies by Ben and Clara); Ben replied there before
    # Clara, and Anna answered his question in the page discussion. Tickets: Anna
    # assigned one to Ben and one to Clara; Ben mentioned Anna in his ticket's thread
    # and she replied; Clara commented on the ticket Anna reported.
    assert reasons == {
        "anna": ["mention", "mention", "reply", "reply", "ticket_comment"],
        "ben": ["assignment", "mention", "reply", "reply", "reply"],
        "clara": ["assignment", "mention"],
    }


async def test_a_direct_message_between_anna_and_ben(demo: dict[str, Any]) -> None:
    clients = demo["clients"]
    dms = (await _get(clients["ben"], "/api/dms"))["items"]
    assert len(dms) == 1
    names = sorted(p["name"] for p in dms[0]["participants"])
    assert names == ["Anna Nord", "Ben Berg"]
    assert [m["author"]["name"] for m in await _top(clients["ben"], dms[0]["id"])] == [
        "Anna Nord",
        "Ben Berg",
    ]
    assert (await _get(clients["clara"], "/api/dms"))["items"] == []


async def test_the_page_discussion_starts_with_system_entries(demo: dict[str, Any]) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    thread = await _get(clara, f"/api/pages/{seeded.page_id}/thread")
    items = await _top(clara, thread["id"])
    kinds = [m["system"]["key"] if m["kind"] == "system" else m["author"]["name"] for m in items]
    assert kinds == [
        "page.created",
        "page.published",
        "page.version_restored",
        "Ben Berg",
    ]
    assert items[-1]["mentions"] == [str(seeded.ids["anna"])]
    assert items[-1]["reply_count"] == 1


async def test_tickets_fill_the_board_in_several_statuses(demo: dict[str, Any]) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    board = await _get(clara, f"/api/spaces/{seeded.space_id}/board")
    columns = {c["status"]["name"]: [t["title"] for t in c["items"]] for c in board["columns"]}
    assert list(columns) == [
        "Neu",
        "In Arbeit",
        "Blockiert",
        "Zur Prüfung",
        "Erledigt",
        "Verworfen",
    ]
    assert {name: len(titles) for name, titles in columns.items()} == {
        "Neu": 7,
        "In Arbeit": 1,
        "Blockiert": 1,
        "Zur Prüfung": 1,
        "Erledigt": 1,
        "Verworfen": 0,
    }
    assert columns["Zur Prüfung"] == ["Urlaubsrechner rundet Teilzeit falsch"]


async def test_an_epic_with_stories_tasks_and_a_bug(demo: dict[str, Any]) -> None:
    seeded, ben = demo["seeded"], demo["clients"]["ben"]
    epics = (await _get(ben, f"/api/spaces/{seeded.space_id}/epics"))["items"]
    assert [(e["title"], e["children"]) for e in epics] == [
        (
            "Projekt Kranich",
            {"open": 2, "active": 0, "review": 1, "done": 0, "cancelled": 0},
        )
    ]
    children = await _get(ben, "/api/tickets", parent=epics[0]["id"], sort="number")
    assert sorted((t["kind"], t["title"]) for t in children["items"]) == [
        ("bug", "Urlaubsrechner rundet Teilzeit falsch"),
        ("story", "Kick-off vorbereiten"),
        ("story", "Prognose erstellen"),
    ]
    story = next(t for t in children["items"] if t["title"] == "Prognose erstellen")
    tasks = await _get(ben, "/api/tickets", parent=story["id"])
    assert sorted((t["title"], t["status"]["name"]) for t in tasks["items"]) == [
        ("Kostenstelle klären", "Blockiert"),
        ("Zahlen für das erste Quartal sammeln", "In Arbeit"),
    ]


async def test_tickets_are_assigned_tagged_and_linked_to_a_page(demo: dict[str, Any]) -> None:
    seeded, clients = demo["seeded"], demo["clients"]
    mine = await _get(clients["ben"], "/api/tickets", assignee="me")
    assert [t["title"] for t in mine["items"]] == ["Zahlen für das erste Quartal sammeln"]
    figures = mine["items"][0]
    assert [t["name"] for t in figures["tags"]] == ["finanzen", "kranich"]
    assert figures["due_on"] is not None and figures["priority"] == "high"
    assert (await _get(clients["clara"], "/api/tickets/counts")) == {"assigned_open": 1}
    linked = await _get(clients["clara"], f"/api/pages/{seeded.page_id}/tickets")
    assert [t["title"] for t in linked["items"]] == ["Urlaubsrechner rundet Teilzeit falsch"]


async def test_ticket_threads_hold_the_timeline_then_comments(demo: dict[str, Any]) -> None:
    seeded, anna = demo["seeded"], demo["clients"]["anna"]
    number = seeded.tickets.numbers["Zahlen für das erste Quartal sammeln"]
    thread = await _get(anna, f"/api/tickets/{number}/thread")
    items = await _top(anna, thread["id"])
    entries = [m["system"]["key"] if m["system"] else m["author"]["name"] for m in items]
    assert entries[-1] == "Ben Berg"
    assert entries[:-1] == [
        "ticket.created",
        "ticket.assigned",
        "ticket.status_changed",
        "ticket.sprint_changed",  # into Sprint 45
        "ticket.sprint_changed",  # carried on into Sprint 46
    ]
    assert items[-1]["mentions"] == [str(seeded.ids["anna"])]
    assert items[-1]["reply_count"] == 1


async def test_a_channel_names_a_ticket_by_its_key(demo: dict[str, Any]) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    number = seeded.tickets.numbers["Zahlen für das erste Quartal sammeln"]
    kranich = await _top(clara, seeded.channels["projekt-kranich"])
    assert f"HC-{number}" in kranich[-1]["body_md"]
    assert kranich[-1]["author"]["name"] == "Anna Nord"


async def test_a_second_run_stops_before_changing_anything(demo: dict[str, Any]) -> None:
    async def nothing() -> None:
        raise AssertionError("must not get this far")

    with pytest.raises(DemoExists):
        await seed(
            demo["connect"],
            admin_email=demo["owner"].email,
            admin_password=PASSWORD,
            people_password=DEMO_PASSWORD,
            settle=nothing,
            wait_seconds=0,
        )


async def test_without_a_worker_the_demo_says_so(
    make_client: Callable[..., Awaitable[AsyncClient]], owner_user: User
) -> None:
    async def connect() -> AsyncClient:
        return await make_client(csrf=True)

    async def no_worker() -> None:
        return None

    with pytest.raises(DemoFailed, match="is the worker running"):
        await seed(
            connect,
            admin_email=owner_user.email,
            admin_password=PASSWORD,
            people_password=DEMO_PASSWORD,
            settle=no_worker,
            wait_seconds=0,
        )


async def test_without_ticket_handlers_the_demo_says_so(
    session: AsyncSession, make_client: Callable[..., Awaitable[AsyncClient]], owner_user: User
) -> None:
    async def connect() -> AsyncClient:
        return await make_client(csrf=True)

    with pytest.raises(DemoFailed, match="ticket thread: is the worker running"):
        await seed(
            connect,
            admin_email=owner_user.email,
            admin_password=PASSWORD,
            people_password=DEMO_PASSWORD,
            settle=lambda: _handle(session, tickets=False),
            wait_seconds=0,
        )


def test_passwords_come_only_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("HERD_DEMO_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("HERD_DEMO_PASSWORD", "short")
    assert main(["--admin", "admin@example.com"]) == 2
    assert "HERD_DEMO_PASSWORD" in capsys.readouterr().out
