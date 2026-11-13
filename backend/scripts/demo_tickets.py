"""The tickets of the demo (M4), in "Team Nord": an extra status „Blockiert", the epic
„Projekt Kranich" with two stories, tasks and a bug in every kind of status, people
assigned, tags, the page „Urlaub" linked, comments in two ticket threads (after the
worker's system entries), and a ticket key mentioned in #projekt-kranich (its card)."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx

from scripts.demo_api import DemoFailed, call, mention, post

EPIC = "Projekt Kranich"
FIGURES = "Zahlen für das erste Quartal sammeln"
TEMPLATE = "Protokollvorlage anlegen"


@dataclass
class SeededTickets:
    numbers: dict[str, int] = field(default_factory=dict)  # by title
    status_ids: dict[str, str] = field(default_factory=dict)  # by name


async def _statuses(admin: httpx.AsyncClient, space_id: str, seeded: SeededTickets) -> None:
    """The defaults, and „Blockiert" (in work, but waiting) right after „In Arbeit"."""
    path = f"/api/spaces/{space_id}/ticket-statuses"
    defaults = (await call(admin, "GET", path))["items"]
    working = next(s for s in defaults if s["name"] == "In Arbeit")
    body = {"name": "Blockiert", "category": "active", "position": working["position"] + 1}
    await call(admin, "POST", path, body)
    for status in (await call(admin, "GET", path))["items"]:
        seeded.status_ids[status["name"]] = str(status["id"])


async def _ticket(
    client: httpx.AsyncClient, space_id: str, seeded: SeededTickets, **body: Any
) -> dict[str, Any]:
    ticket: dict[str, Any] = await call(client, "POST", f"/api/spaces/{space_id}/tickets", body)
    seeded.numbers[ticket["title"]] = int(ticket["number"])
    return ticket


async def _move(client: httpx.AsyncClient, ticket: dict[str, Any], status_id: str) -> None:
    body = {"status_id": status_id, "version": ticket["version"]}
    ticket.update(await call(client, "PATCH", f"/api/tickets/{ticket['number']}", body))


async def _tag(client: httpx.AsyncClient, ticket: dict[str, Any], *tag_ids: str) -> None:
    body = {"tag_ids": list(tag_ids), "version": ticket["version"]}
    ticket.update(await call(client, "PUT", f"/api/tickets/{ticket['number']}/tags", body))


def _person(ids: dict[str, str], key: str) -> dict[str, str]:
    return {"type": "user", "id": ids[key]}


async def build(
    admin: httpx.AsyncClient,
    people: dict[str, httpx.AsyncClient],
    *,
    space_id: str,
    page_id: str,
    ids: dict[str, str],
    channel_id: str,
) -> SeededTickets:
    """The statuses, tickets, tags, the page link and the card in the channel."""
    seeded = SeededTickets()
    anna, ben = people["anna"], people["ben"]
    await _statuses(admin, space_id, seeded)
    tags = {}
    for name, color in (("kranich", "#2563eb"), ("finanzen", "#16a34a")):
        tag = await call(
            anna, "POST", "/api/tags", {"name": name, "color": color, "space_id": space_id}
        )
        tags[name] = str(tag["id"])

    epic = await _ticket(
        anna,
        space_id,
        seeded,
        title=EPIC,
        kind="epic",
        priority="high",
        description_md="Neues Planungsprojekt: Kick-off, Prognose, Protokolle.",
    )
    await _tag(anna, epic, tags["kranich"])
    kickoff = await _ticket(
        anna, space_id, seeded, title="Kick-off vorbereiten", kind="story", parent_id=epic["id"]
    )
    forecast = await _ticket(
        anna, space_id, seeded, title="Prognose erstellen", kind="story", parent_id=epic["id"]
    )

    figures = await _ticket(
        anna,
        space_id,
        seeded,
        title=FIGURES,
        parent_id=forecast["id"],
        priority="high",
        due_on=(date.today() + timedelta(days=7)).isoformat(),
        assignee=_person(ids, "ben"),
        description_md="Umsatz und Kosten je Monat, **Quelle**: Vertrieb und Buchhaltung.",
    )
    await _tag(anna, figures, tags["kranich"], tags["finanzen"])
    await _move(ben, figures, seeded.status_ids["In Arbeit"])  # Ben starts on it

    room = await _ticket(
        anna,
        space_id,
        seeded,
        title="Raum für den Kick-off buchen",
        parent_id=kickoff["id"],
        assignee=_person(ids, "anna"),
    )
    await _move(anna, room, seeded.status_ids["Erledigt"])
    await _ticket(
        anna,
        space_id,
        seeded,
        title=TEMPLATE,
        parent_id=kickoff["id"],
        priority="low",
        assignee=_person(ids, "clara"),
    )
    cost = await _ticket(
        anna,
        space_id,
        seeded,
        title="Kostenstelle klären",
        parent_id=forecast["id"],
        assignee=_person(ids, "anna"),
    )
    await _tag(anna, cost, tags["finanzen"])
    await _move(anna, cost, seeded.status_ids["Blockiert"])
    bug = await _ticket(
        ben,
        space_id,
        seeded,
        title="Urlaubsrechner rundet Teilzeit falsch",
        kind="bug",
        parent_id=epic["id"],
        priority="urgent",
        description_md="Bei 3 Tagen pro Woche zeigt er 17 statt 18 Tage.",
    )
    await call(ben, "PUT", f"/api/tickets/{bug['number']}/pages/{page_id}")
    await _move(ben, bug, seeded.status_ids["Zur Prüfung"])
    await _ticket(
        ben, space_id, seeded, title="Teilnehmerliste verschicken", parent_id=kickoff["id"]
    )  # open, nobody on it yet

    # A ticket key in a channel: readers of the ticket see its card under the message.
    await post(
        anna, channel_id, f"Stand der Zahlen steht in {figures['key']}, bitte dort kommentieren."
    )
    return seeded


async def thread_of(client: httpx.AsyncClient, number: int) -> str:
    return str((await call(client, "GET", f"/api/tickets/{number}/thread"))["id"])


async def created_entry(client: httpx.AsyncClient, number: int, *, wait_seconds: float) -> None:
    """Waits until the worker wrote the ticket's first system entry (DemoFailed after
    `wait_seconds`; 0 checks once), so that comments follow it."""
    deadline = time.monotonic() + wait_seconds
    path = f"/api/conversations/{await thread_of(client, number)}/messages"
    while True:
        items = (await call(client, "GET", path))["items"]
        if any(m["kind"] == "system" for m in items):
            return
        if time.monotonic() >= deadline:
            raise DemoFailed("no system entries in the ticket thread: is the worker running?")
        await asyncio.sleep(0.5)


async def comment(
    people: dict[str, httpx.AsyncClient],
    seeded: SeededTickets,
    ids: dict[str, str],
    *,
    settle: Callable[[], Awaitable[None]],
    wait_seconds: float,
) -> None:
    """Ben asks Anna in the figures' thread, she answers in a reply; Clara comments on
    the template she was given."""
    anna, ben, clara = people["anna"], people["ben"], people["clara"]
    await settle()
    for title in (FIGURES, TEMPLATE):
        await created_entry(ben, seeded.numbers[title], wait_seconds=wait_seconds)
    figures = await thread_of(ben, seeded.numbers[FIGURES])
    question = await post(
        ben,
        figures,
        f"{mention('Anna Nord', ids['anna'])}, die Zahlen vom Vertrieb fehlen noch. Hast du sie?",
        mentions=(ids["anna"],),
    )
    await post(anna, figures, "Kommen morgen früh per Mail.", parent_id=question)
    template = await thread_of(clara, seeded.numbers[TEMPLATE])
    await post(clara, template, "Ich nehme die Vorlage vom letzten Projekt als Grundlage.")
