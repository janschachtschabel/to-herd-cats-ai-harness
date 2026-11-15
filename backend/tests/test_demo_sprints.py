"""The demo's sprints (scripts/demo_sprints.py, M4b) in "Team Nord": one closed with
its tally, one running, one planned, tickets in each and a backlog; the running sprint
fills the daily view. The demo itself comes from the fixture of test_demo_seed."""

from typing import Any

from tests.test_demo_seed import _get, demo  # noqa: F401 -- the fixture

FIGURES = "Zahlen für das erste Quartal sammeln"


async def _sprints(client: Any, space_id: str) -> dict[str, dict[str, Any]]:
    page = await _get(client, f"/api/spaces/{space_id}/sprints")
    return {s["name"]: s for s in page["items"]}


async def _titles(client: Any, **params: Any) -> list[str]:
    page = await _get(client, "/api/tickets", limit=100, **params)
    return sorted(t["title"] for t in page["items"])


async def test_one_sprint_closed_with_its_tally_one_running_one_planned(
    demo: dict[str, Any],  # noqa: F811
) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    page = await _get(clara, f"/api/spaces/{seeded.space_id}/sprints")
    assert [(s["name"], s["state"], s["tally"]) for s in page["items"]] == [
        ("Sprint 46", "active", None),
        ("Sprint 47", "planned", None),
        ("Sprint 45", "closed", {"planned": 3, "done": 1, "carried": 2}),
    ]
    running = page["items"][0]
    assert running["goal"] and running["starts_on"] < running["ends_on"]


async def test_tickets_sit_in_each_sprint_and_the_rest_in_the_backlog(
    demo: dict[str, Any],  # noqa: F811
) -> None:
    seeded, ben = demo["seeded"], demo["clients"]["ben"]
    sprints = await _sprints(ben, seeded.space_id)
    # Done in Sprint 45 stays there; its unfinished went on into Sprint 46.
    assert await _titles(ben, sprint=sprints["Sprint 45"]["id"]) == ["Raum für den Kick-off buchen"]
    assert await _titles(ben, sprint=sprints["Sprint 46"]["id"]) == [
        "Kostenstelle klären",
        "Protokollvorlage anlegen",
        "Urlaubsrechner rundet Teilzeit falsch",
        FIGURES,
    ]
    assert await _titles(ben, sprint=sprints["Sprint 47"]["id"]) == ["Teilnehmerliste verschicken"]
    assert await _titles(ben, sprint="none") == [
        "Feedbackrunde nach dem Kick-off planen",
        "Folien für den Kick-off",
        "Kick-off vorbereiten",
        "Prognose erstellen",
        "Projekt Kranich",
    ]


async def test_the_running_sprint_fills_the_daily_view(
    demo: dict[str, Any],  # noqa: F811
) -> None:
    seeded, anna = demo["seeded"], demo["clients"]["anna"]
    running = (await _sprints(anna, seeded.space_id))["Sprint 46"]
    board = await _get(
        anna,
        f"/api/spaces/{seeded.space_id}/board",
        group_by="assignee",
        sprint=running["id"],
    )
    rows = {
        (row["assignee"] or {}).get("name"): sum(cell["count"] for cell in row["cells"])
        for row in board["rows"]
    }
    assert rows == {"Anna Nord": 1, "Ben Berg": 1, "Clara Klein": 1, None: 1}
    # All of it happened today: every card of the running sprint is marked.
    assert all(cell["changed"] == cell["count"] for row in board["rows"] for cell in row["cells"])


async def test_the_ticket_thread_tells_the_sprint_moves(
    demo: dict[str, Any],  # noqa: F811
) -> None:
    seeded, anna = demo["seeded"], demo["clients"]["anna"]
    number = seeded.tickets.numbers[FIGURES]
    thread = await _get(anna, f"/api/tickets/{number}/thread")
    page = await _get(anna, f"/api/conversations/{thread['id']}/messages", limit=100)
    moves = [
        (m["system"]["old"], m["system"]["new"])
        for m in reversed(page["items"])
        if m["system"] and m["system"]["key"] == "ticket.sprint_changed"
    ]
    names = [(old and old["name"], new and new["name"]) for old, new in moves]
    assert names == [(None, "Sprint 45"), ("Sprint 45", "Sprint 46")]
