"""The sprints of the demo (M4b), in "Team Nord": „Sprint 45" ran three weeks ago and is
closed (its unfinished tickets went on into the next sprint, its tally kept),
„Sprint 46" runs now and fills the daily view, „Sprint 47" is planned; two new tasks
and the epic with its stories stay in the backlog. Anna (moderator) plans the sprints
and puts the tickets in, through the public API."""

from datetime import date, timedelta
from typing import Any

import httpx

from scripts.demo_api import call
from scripts.demo_tickets import FIGURES, TEMPLATE, SeededTickets

KICKOFF = "Kick-off vorbereiten"
BACKLOG = ("Feedbackrunde nach dem Kick-off planen", "Folien für den Kick-off")
# name, goal, first day (days from today), tickets put in while planned; two weeks each
SPRINTS: tuple[tuple[str, str, int, tuple[str, ...]], ...] = (
    (
        "Sprint 45",
        "Kick-off organisiert, Zahlen angefragt",
        -21,
        ("Raum für den Kick-off buchen", "Kostenstelle klären", FIGURES),
    ),
    (
        "Sprint 46",
        "Prognose steht, Fehler im Urlaubsrechner behoben",
        -7,
        ("Urlaubsrechner rundet Teilzeit falsch", TEMPLATE),
    ),
    ("Sprint 47", "Kick-off durchführen", 7, ("Teilnehmerliste verschicken",)),
)


async def _into(
    client: httpx.AsyncClient, seeded: SeededTickets, title: str, sprint_id: str
) -> None:
    number = seeded.numbers[title]
    ticket = await call(client, "GET", f"/api/tickets/{number}")
    body = {"sprint_id": sprint_id, "version": ticket["version"]}
    await call(client, "PATCH", f"/api/tickets/{number}", body)


async def _backlog(client: httpx.AsyncClient, space_id: str, seeded: SeededTickets) -> None:
    """Two tasks of the kick-off story that no sprint holds yet."""
    path = f"/api/spaces/{space_id}/tickets"
    kickoff = await call(client, "GET", f"/api/tickets/{seeded.numbers[KICKOFF]}")
    for title in BACKLOG:
        ticket = await call(client, "POST", path, {"title": title, "parent_id": kickoff["id"]})
        seeded.numbers[title] = int(ticket["number"])


async def build(
    people: dict[str, httpx.AsyncClient], *, space_id: str, seeded: SeededTickets
) -> dict[str, str]:
    """Plans the three sprints, fills them, runs and closes the first (unfinished into
    the next), starts the second. Returns the sprint ids by name."""
    anna = people["anna"]
    await _backlog(anna, space_id, seeded)
    today = date.today()
    sprints: dict[str, dict[str, Any]] = {}
    for name, goal, offset, titles in SPRINTS:
        body = {
            "name": name,
            "goal": goal,
            "starts_on": (today + timedelta(days=offset)).isoformat(),
            "ends_on": (today + timedelta(days=offset + 13)).isoformat(),
        }
        sprint = await call(anna, "POST", f"/api/spaces/{space_id}/sprints", body)
        sprints[name] = sprint
        for title in titles:
            await _into(anna, seeded, title, str(sprint["id"]))

    first = sprints["Sprint 45"]
    started = await call(
        anna, "POST", f"/api/sprints/{first['id']}/start", {"version": first["version"]}
    )
    close = {"version": started["version"], "move_open_to": "next"}  # next: Sprint 46
    await call(anna, "POST", f"/api/sprints/{first['id']}/close", close)
    planned = await call(anna, "GET", f"/api/spaces/{space_id}/sprints?state=planned")
    nearest = planned["items"][0]  # earliest first: Sprint 46, read again after the close
    await call(anna, "POST", f"/api/sprints/{nearest['id']}/start", {"version": nearest["version"]})
    return {name: str(sprint["id"]) for name, sprint in sprints.items()}
