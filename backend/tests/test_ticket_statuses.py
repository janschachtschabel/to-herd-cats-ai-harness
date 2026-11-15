"""The status workflow per space (plan M4 task 1): five statuses with every space, the
rights to read and to manage them, the rules that keep a space workable, versions."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.spaces.models import Space
from app.modules.tickets.models import WorkItem
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, status_of, statuses, ticket_row

DEFAULTS = [
    ("Neu", "open"),
    ("In Arbeit", "active"),
    ("Zur Prüfung", "review"),
    ("Erledigt", "done"),
    ("Verworfen", "cancelled"),
]


def _shape(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(s["name"], s["category"]) for s in items]


async def _create(client: AsyncClient, space_id: object, **body: Any) -> Any:
    return await client.post(f"/api/spaces/{space_id}/ticket-statuses", json=body)


async def _update(client: AsyncClient, status: dict[str, Any], **body: Any) -> Any:
    return await client.patch(
        f"/api/ticket-statuses/{status['id']}", json={"version": status["version"], **body}
    )


async def _delete(client: AsyncClient, status: dict[str, Any], **params: Any) -> Any:
    query = {"version": status["version"], **params}
    return await client.delete(f"/api/ticket-statuses/{status['id']}", params=query)


async def test_a_space_made_through_the_api_has_the_five_statuses(
    member_client: AsyncClient,
) -> None:
    space = (await member_client.post("/api/spaces", json={"kind": "team", "name": "T"})).json()
    items = await statuses(member_client, space["id"])
    assert _shape(items) == DEFAULTS
    assert [s["position"] for s in items] == [0, 1, 2, 3, 4]
    assert {s["version"] for s in items} == {1}


async def test_every_space_has_them_whoever_inserts_it(
    make_space: MakeSpace, owner: AsyncClient
) -> None:
    space = await make_space("open", "Direkt")  # straight into the table
    assert _shape(await statuses(owner, space.id)) == DEFAULTS


async def test_reading_needs_a_role_in_a_team_space(desk: Desk) -> None:
    for name in ("viewer", "editor", "manager", "admin"):
        assert len(await statuses(desk.clients[name], desk.space_id)) == 5, name
    r = await desk.outsider.get(f"/api/spaces/{desk.space_id}/ticket-statuses")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "space.not_found"


async def test_the_list_pages(desk: Desk) -> None:
    url = f"/api/spaces/{desk.space_id}/ticket-statuses"
    first = (await desk.viewer.get(url, params={"limit": 2})).json()
    assert [s["name"] for s in first["items"]] == ["Neu", "In Arbeit"]
    second = (
        await desk.viewer.get(url, params={"limit": 3, "cursor": first["next_cursor"]})
    ).json()
    assert [s["name"] for s in second["items"]] == ["Zur Prüfung", "Erledigt", "Verworfen"]
    assert second["next_cursor"] is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [("manager", 201), ("admin", 201), ("moderator", 403), ("editor", 403), ("viewer", 403)],
)
async def test_managing_needs_space_manage(desk: Desk, name: str, expected: int) -> None:
    r = await _create(desk.clients[name], desk.space_id, name=f"Neu {name}", category="active")
    assert r.status_code == expected, r.text
    status = await status_of(desk.manager, desk.space_id, "review")
    assert (await _update(desk.clients[name], status, name=f"P {name}")).status_code in (
        200 if expected == 201 else 403,
    )


async def test_a_status_of_an_unseen_space_does_not_exist(desk: Desk) -> None:
    status = await status_of(desk.manager, desk.space_id, "review")
    for response in (
        await _update(desk.outsider, status, name="X"),
        await _delete(desk.outsider, status),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ticket_status.not_found"


async def test_create_puts_it_where_asked_and_moves_the_others(desk: Desk) -> None:
    r = await _create(desk.manager, desk.space_id, name="Blockiert", category="active", position=2)
    assert r.status_code == 201, r.text
    assert r.json()["position"] == 2
    names = [s["name"] for s in await statuses(desk.viewer, desk.space_id)]
    assert names == ["Neu", "In Arbeit", "Blockiert", "Zur Prüfung", "Erledigt", "Verworfen"]
    last = await _create(desk.manager, desk.space_id, name="Archiv", category="done")
    assert last.json()["position"] == 6


async def test_names_are_unique_in_a_space_ignoring_case(desk: Desk, make_space: MakeSpace) -> None:
    r = await _create(desk.manager, desk.space_id, name="  erledigt ", category="done")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ticket_status.name_taken"
    status = await status_of(desk.manager, desk.space_id, "review")
    r = await _update(desk.manager, status, name="NEU")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ticket_status.name_taken"
    assert (
        await _create(desk.manager, desk.space_id, name="Warten", category="active")
    ).status_code == 201
    other = await make_space("open", "Anderswo")
    assert (
        await _create(desk.admin, other.id, name="Warten", category="active")
    ).status_code == 201


async def test_names_are_one_line_of_at_most_40_characters(desk: Desk) -> None:
    for name in ("", "  ", "a\nb", "x" * 41):
        r = await _create(desk.manager, desk.space_id, name=name, category="open")
        assert r.status_code == 422, name


async def test_at_most_twenty_statuses(desk: Desk) -> None:
    for i in range(15):
        r = await _create(desk.manager, desk.space_id, name=f"S{i}", category="active")
        assert r.status_code == 201, r.text
    r = await _create(desk.manager, desk.space_id, name="S21", category="active")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ticket_status.too_many"


async def test_rename_recategorise_and_move(desk: Desk) -> None:
    status = await status_of(desk.manager, desk.space_id, "review")
    r = await _update(desk.manager, status, name="Review", category="active", position=0)
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["category"], r.json()["position"]) == (
        "Review",
        "active",
        0,
    )
    assert r.json()["version"] == status["version"] + 1
    names = [s["name"] for s in await statuses(desk.viewer, desk.space_id)]
    assert names == ["Review", "Neu", "In Arbeit", "Erledigt", "Verworfen"]
    again = await _update(desk.manager, r.json(), name="Review")
    assert again.json()["version"] == r.json()["version"]  # nothing changed


async def test_an_old_version_is_a_conflict(desk: Desk) -> None:
    status = await status_of(desk.manager, desk.space_id, "review")
    assert (await _update(desk.manager, status, name="Prüfen")).status_code == 200
    for response in (
        await _update(desk.manager, status, name="Prüfung"),
        await _delete(desk.manager, status),
    ):
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "ticket_status.version_conflict"
        assert error["details"] == {"current_version": status["version"] + 1}


async def test_a_space_keeps_an_open_and_a_done_status(desk: Desk) -> None:
    for category in ("open", "done"):
        only = await status_of(desk.manager, desk.space_id, category)
        r = await _update(desk.manager, only, category="active")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "ticket_status.category_required"
        r = await _delete(desk.manager, only)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "ticket_status.category_required"
    second = await _create(desk.manager, desk.space_id, name="Auch neu", category="open")
    first = await status_of(desk.manager, desk.space_id, "open")
    assert (await _delete(desk.manager, first)).status_code == 204
    assert (await _update(desk.manager, second.json(), category="active")).status_code == 409


async def test_delete_without_tickets(desk: Desk) -> None:
    status = await status_of(desk.manager, desk.space_id, "review")
    assert (await _delete(desk.manager, status)).status_code == 204
    items = await statuses(desk.viewer, desk.space_id)
    assert [s["name"] for s in items] == ["Neu", "In Arbeit", "Erledigt", "Verworfen"]
    assert [s["position"] for s in items] == [0, 1, 2, 3]


async def test_delete_with_tickets_needs_a_replacement_of_the_same_space(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    review = await status_of(desk.manager, desk.space_id, "review")
    active = await status_of(desk.manager, desk.space_id, "active")
    item = await ticket_row(session, desk.space, desk.users["editor"], status_id=review["id"])
    r = await _delete(desk.manager, review)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ticket_status.in_use"
    elsewhere: Space = await make_space("open", "Fremd")
    foreign = await status_of(desk.admin, elsewhere.id, "active")
    for bad in (foreign["id"], review["id"], "019a0000-0000-7000-8000-000000000000"):
        r = await _delete(desk.manager, review, replace_with=bad)
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "ticket_status.replacement_invalid"
    r = await _delete(desk.manager, review, replace_with=active["id"])
    assert r.status_code == 204, r.text
    moved = await session.scalar(
        select(WorkItem).where(WorkItem.id == item.id).execution_options(populate_existing=True)
    )
    assert moved is not None
    assert (str(moved.status_id), moved.version) == (active["id"], 2)


async def test_changes_are_audited(desk: Desk, session: AsyncSession) -> None:
    created = (await _create(desk.manager, desk.space_id, name="Neu 2", category="open")).json()
    updated = (await _update(desk.manager, created, name="Neu 3")).json()
    assert (await _delete(desk.manager, updated)).status_code == 204
    rows = await session.scalars(
        select(AuditLog.action).where(AuditLog.target_type == "ticket_status").order_by(AuditLog.id)
    )
    assert list(rows) == [
        "ticket_status.created",
        "ticket_status.updated",
        "ticket_status.deleted",
    ]
