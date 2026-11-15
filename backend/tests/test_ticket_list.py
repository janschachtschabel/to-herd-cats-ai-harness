"""The ticket list across spaces (plan M4 task 2): only tickets of spaces where the
caller may read tickets, filtered in SQL, with filters, sort orders and cursors."""

from typing import Any

import pytest
from httpx import AsyncClient

from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of


async def _list(client: AsyncClient, **params: Any) -> list[dict[str, Any]]:
    r = await client.get("/api/tickets", params=params)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def _all(client: AsyncClient, **params: Any) -> list[dict[str, Any]]:
    """Every page, following the cursor."""
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        r = await client.get("/api/tickets", params=query)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        cursor = r.json()["next_cursor"]
        if cursor is None:
            return items


def _titles(items: list[dict[str, Any]]) -> list[str]:
    return [t["title"] for t in items]


async def test_a_hidden_space_s_tickets_never_show(desk: Desk, make_space: MakeSpace) -> None:
    """The leak test of the list: every filter and sort, for someone without the space.
    (Mutation probe: without the space filter in the repository, this fails.)"""
    secret = await make_space("team", "Geheim")
    hidden = await new_ticket(
        desk.admin,
        secret.id,
        "Geheimsache Apfel",
        kind="epic",
        priority="urgent",
        due_on="2026-01-01",
        assignee={"type": "user", "id": desk.id_of("admin")},
    )
    await new_ticket(desk.editor, desk.space_id, "Sichtbar Apfel")
    filters: list[dict[str, Any]] = [
        {},
        {"q": "Apfel"},
        {"space_id": str(secret.id)},
        {"kind": "epic"},
        {"priority": "urgent"},
        {"due_before": "2027-01-01"},
        {"assignee": desk.id_of("admin")},
        {"reporter": desk.id_of("admin")},
        {"status_category": "open"},
        {"status_id": hidden["status"]["id"]},
    ]
    for sort in ("updated", "due", "priority", "number"):
        for query in filters:
            items = await _all(desk.outsider, sort=sort, **query)
            assert hidden["id"] not in {t["id"] for t in items}, (sort, query)
    assert _titles(await _list(desk.outsider, q="Apfel")) == []
    assert _titles(await _list(desk.viewer, q="Apfel")) == ["Sichtbar Apfel"]
    assert hidden["id"] in {t["id"] for t in await _list(desk.admin, q="Apfel")}


async def test_items_carry_what_a_row_shows(desk: Desk) -> None:
    epic = await new_ticket(desk.editor, desk.space_id, "Epos", kind="epic")
    await new_ticket(
        desk.moderator,
        desk.space_id,
        "Teil",
        kind="story",
        parent_id=epic["id"],
        assignee={"type": "user", "id": desk.id_of("editor")},
        due_on="2027-03-01",
    )
    (item,) = await _list(desk.viewer, kind="story")
    assert item["key"].startswith("HC-")
    assert item["parent"]["id"] == epic["id"]
    assert item["assignee"]["name"] == "Desk editor"
    assert item["reporter"]["name"] == "Desk moderator"
    assert item["status"]["category"] == "open"
    assert item["due_on"] == "2027-03-01"
    assert "description_md" not in item


async def test_filters(desk: Desk, make_space: MakeSpace) -> None:
    other = await make_space("open", "Offen")
    done = await status_of(desk.viewer, desk.space_id, "done")
    review = await status_of(desk.viewer, desk.space_id, "review")
    epic = await new_ticket(desk.editor, desk.space_id, "Epos", kind="epic")
    mine = {"type": "user", "id": desk.id_of("editor")}
    await new_ticket(desk.editor, desk.space_id, "A", assignee=mine, parent_id=epic["id"])
    await new_ticket(desk.editor, desk.space_id, "B", status_id=done["id"], priority="high")
    await new_ticket(desk.moderator, desk.space_id, "C", status_id=review["id"], kind="bug")
    await new_ticket(desk.editor2, desk.space_id, "D", due_on="2026-12-01", assignee=None)
    await new_ticket(desk.admin, other.id, "E Druckerwartung", description_md="Toner leer")
    me = desk.editor
    assert _titles(await _list(me, assignee="me")) == ["A"]
    assert _titles(await _list(desk.viewer, assignee=desk.id_of("editor"))) == ["A"]
    assert set(_titles(await _list(me, reporter="me"))) == {"Epos", "A", "B"}
    assert _titles(await _list(me, space_id=str(other.id))) == ["E Druckerwartung"]
    assert set(_titles(await _list(me, status_category=["done", "review"]))) == {"B", "C"}
    assert _titles(await _list(me, status_id=done["id"])) == ["B"]
    assert _titles(await _list(me, kind="bug")) == ["C"]
    assert _titles(await _list(me, priority="high")) == ["B"]
    assert _titles(await _list(me, parent=epic["id"])) == ["A"]
    assert _titles(await _list(me, due_before="2026-12-02")) == ["D"]
    assert _titles(await _list(me, q="Toner")) == ["E Druckerwartung"]
    assert _titles(await _list(me, q="Druckerwartungen")) == ["E Druckerwartung"]  # stems


async def test_sort_orders_and_cursors(desk: Desk) -> None:
    made = []
    for title, priority, due in (
        ("eins", "low", "2027-01-03"),
        ("zwei", "urgent", None),
        ("drei", "normal", "2027-01-01"),
        ("vier", "urgent", "2027-01-02"),
        ("fünf", "high", None),
    ):
        made.append(
            await new_ticket(desk.editor, desk.space_id, title, priority=priority, due_on=due)
        )
    await patch(desk.editor, made[0], title="eins!")  # the latest change
    by_number = await _all(desk.viewer, sort="number", limit=2)
    assert _titles(by_number) == ["fünf", "vier", "drei", "zwei", "eins!"]
    by_due = await _all(desk.viewer, sort="due", limit=2)
    assert _titles(by_due) == ["drei", "vier", "eins!", "zwei", "fünf"]  # no date last
    by_priority = await _all(desk.viewer, sort="priority", limit=2)
    assert _titles(by_priority) == ["vier", "zwei", "fünf", "drei", "eins!"]
    by_update = await _all(desk.viewer, limit=2)  # the default: last changed first
    assert _titles(by_update)[0] == "eins!"
    assert sorted(_titles(by_update)) == sorted(_titles(by_number))


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 101},
        {"limit": 0},
        {"sort": "title"},
        {"cursor": "nonsense"},
        {"cursor": "WyJkdWUiLCAxLCAyXQ"},  # a cursor of another sort order
        {"assignee": "someone"},
        {"status_category": "later"},
        {"due_before": "soon"},
    ],
)
async def test_bad_parameters_are_422(desk: Desk, params: dict[str, Any]) -> None:
    r = await desk.viewer.get("/api/tickets", params=params)
    assert r.status_code == 422, r.text
