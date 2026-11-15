"""Sprints per space (plan M4b task 1, decisions 1 and 2): made, changed, started and
closed by whoever may assign tickets in the space (`ticket.assign`, from moderator);
seen by whoever may read its tickets, anyone else gets 404 `sprint.not_found`, as for
an id nobody has. At most one sprint per space is active. Every change names the
version it read (409), is one `sprint.*` event (ids only) and, where it creates,
starts or closes, audited."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.core.principal import Principal
from app.modules.audit.models import AuditLog
from app.modules.spaces.repository import SpaceRepository
from tests.factories_spaces import MakeSpace
from tests.factories_sprints import close, new_sprint, sprints, start, started
from tests.factories_tickets import Desk


async def test_who_may_make_change_start_and_close_a_sprint(desk: Desk) -> None:
    url = f"/api/spaces/{desk.space_id}/sprints"
    body = {"name": "S", "starts_on": "2026-11-16", "ends_on": "2026-11-27"}
    for name in ("editor", "viewer"):
        r = await desk.clients[name].post(url, json=body)
        assert r.status_code == 403, name
        assert r.json()["error"]["code"] == "auth.permission_denied"
    r = await desk.outsider.post(url, json=body)
    assert (r.status_code, r.json()["error"]["code"]) == (404, "space.not_found")
    made = [await new_sprint(desk.clients[n], desk.space_id, n) for n in ("moderator", "manager")]
    made.append(await new_sprint(desk.admin, desk.space_id, "admin"))
    sprint = made[0]
    assert sprint["state"] == "planned" and sprint["version"] == 1 and sprint["tally"] is None
    assert (sprint["space_id"], sprint["goal"]) == (desk.space_id, "")
    patch_url = f"/api/sprints/{sprint['id']}"
    for name in ("editor", "viewer"):
        client = desk.clients[name]
        r = await client.patch(patch_url, json={"name": "X", "version": 1})
        assert r.status_code == 403, name
        assert (await start(client, sprint)).status_code == 403
        assert (await close(client, sprint, "backlog")).status_code == 403
    for r in (
        await desk.outsider.patch(patch_url, json={"name": "X", "version": 1}),
        await start(desk.outsider, sprint),
        await close(desk.outsider, sprint, "backlog"),
    ):
        assert (r.status_code, r.json()["error"]["code"]) == (404, "sprint.not_found")
    r = await desk.moderator.patch(
        patch_url, json={"name": "Neu", "goal": "Fertig werden", "version": 1}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["goal"], r.json()["version"]) == ("Neu", "Fertig werden", 2)
    stale = await desk.moderator.patch(patch_url, json={"name": "Alt", "version": 1})
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "sprint.version_conflict")
    assert [s["name"] for s in await sprints(desk.viewer, desk.space_id)]  # viewers read


async def test_dates_and_names_are_checked(desk: Desk) -> None:
    url = f"/api/spaces/{desk.space_id}/sprints"
    for body in (
        {"name": "", "starts_on": "2026-11-16", "ends_on": "2026-11-27"},
        {"name": "x" * 81, "starts_on": "2026-11-16", "ends_on": "2026-11-27"},
        {"name": "S", "goal": "g" * 501, "starts_on": "2026-11-16", "ends_on": "2026-11-27"},
        {"name": "S", "starts_on": "2026-11-16"},
        {"name": "S", "starts_on": "2026-11-16", "ends_on": "2026-11-27", "state": "active"},
    ):
        assert (await desk.moderator.post(url, json=body)).status_code == 422, body
    r = await desk.moderator.post(
        url, json={"name": "S", "starts_on": "2026-11-27", "ends_on": "2026-11-26"}
    )
    assert (r.status_code, r.json()["error"]["code"]) == (422, "sprint.dates_invalid")
    sprint = await new_sprint(desk.moderator, desk.space_id, starts_on="2026-11-27")
    r = await desk.moderator.patch(
        f"/api/sprints/{sprint['id']}", json={"ends_on": "2026-11-20", "version": 1}
    )
    assert (r.status_code, r.json()["error"]["code"]) == (422, "sprint.dates_invalid")


async def test_one_active_sprint_per_space_and_the_states_in_order(
    desk: Desk, make_space: MakeSpace
) -> None:
    first = await new_sprint(desk.moderator, desk.space_id, "Eins")
    second = await new_sprint(desk.moderator, desk.space_id, "Zwei")
    r = await start(desk.moderator, first)
    assert r.status_code == 200, r.text
    first = r.json()
    assert (first["state"], first["version"]) == ("active", 2)
    again = await start(desk.moderator, second)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "sprint.active_exists")
    twice = await start(desk.moderator, first)
    assert (twice.status_code, twice.json()["error"]["code"]) == (409, "sprint.state_invalid")
    planned = await close(desk.moderator, second, "backlog")
    assert (planned.status_code, planned.json()["error"]["code"]) == (409, "sprint.state_invalid")
    other = await make_space("team", "Anders", members=[(desk.users["moderator"], "moderator")])
    await started(desk.moderator, other.id)  # another space has its own active sprint
    r = await close(desk.moderator, first, "backlog")
    assert r.status_code == 200, r.text
    closed = r.json()
    assert closed["state"] == "closed"
    assert closed["tally"] == {"planned": 0, "done": 0, "carried": 0}
    r = await desk.moderator.patch(
        f"/api/sprints/{closed['id']}", json={"name": "X", "version": closed["version"]}
    )
    assert (r.status_code, r.json()["error"]["code"]) == (409, "sprint.state_invalid")
    assert (await start(desk.moderator, closed)).json()["error"]["code"] == "sprint.state_invalid"
    assert (await start(desk.moderator, second)).status_code == 200  # the next may start


async def test_the_list_orders_active_planned_closed_and_pages(desk: Desk) -> None:
    late = await new_sprint(desk.moderator, desk.space_id, "Spät", "2027-01-04", "2027-01-15")
    soon = await new_sprint(desk.moderator, desk.space_id, "Bald", "2026-12-07", "2026-12-18")
    older = await new_sprint(desk.moderator, desk.space_id, "Älter", "2026-10-05", "2026-10-16")
    older = (
        await close(desk.moderator, (await start(desk.moderator, older)).json(), "next")
    ).json()
    old = await new_sprint(desk.moderator, desk.space_id, "Alt", "2026-10-19", "2026-10-30")
    old = (await close(desk.moderator, (await start(desk.moderator, old)).json(), "next")).json()
    running = await started(desk.moderator, desk.space_id, "Jetzt")
    listed = await sprints(desk.viewer, desk.space_id, limit=2)
    assert [s["name"] for s in listed] == ["Jetzt", "Bald", "Spät", "Alt", "Älter"]
    assert listed[0]["id"] == running["id"] and listed[1]["id"] == soon["id"]
    assert {late["id"], old["id"], older["id"]} < {s["id"] for s in listed}
    only = await sprints(desk.viewer, desk.space_id, state=["planned", "active"])
    assert [s["name"] for s in only] == ["Jetzt", "Bald", "Spät"]
    r = await desk.viewer.get(f"/api/spaces/{desk.space_id}/sprints", params={"cursor": "x"})
    assert r.status_code == 422


async def test_a_sprint_of_a_hidden_space_does_not_exist(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    """Review focus 1 (mutation probe: without the scope in the sprint repository, the
    outsider and the former member find the sprint and get 403 or 200, not 404)."""
    secret = await make_space("team", "Geheim", members=[(desk.users["moderator"], "moderator")])
    sprint = await new_sprint(desk.moderator, secret.id, "Geheim")
    unknown = {**sprint, "id": str(uuid.uuid4())}
    for client in (desk.outsider, desk.manager):  # manager: admin of desk, not of secret
        answers = []
        for target in (sprint, unknown):
            for r in (
                await client.patch(f"/api/sprints/{target['id']}", json={"version": 1}),
                await start(client, target),
                await close(client, target, "next"),
            ):
                assert r.status_code == 404, r.text
                error = r.json()["error"]
                answers.append((error["code"], error["message"]))
        assert set(answers) == {answers[0]} and answers[0][0] == "sprint.not_found"
        r = await client.get(f"/api/spaces/{secret.id}/sprints")
        assert (r.status_code, r.json()["error"]["code"]) == (404, "space.not_found")
    await SpaceRepository(session).remove_member(
        secret.id, Principal.user(desk.users["moderator"].id)
    )
    r = await start(desk.moderator, sprint)
    assert (r.status_code, r.json()["error"]["code"]) == (404, "sprint.not_found")
    r = await desk.moderator.get(f"/api/spaces/{secret.id}/sprints")
    assert r.status_code == 404


async def test_each_change_is_one_event_with_ids_only_and_audited(
    desk: Desk, session: AsyncSession
) -> None:
    sprint = await new_sprint(desk.moderator, desk.space_id, "Geheimer Name", goal="Geheim")
    r = await desk.moderator.patch(
        f"/api/sprints/{sprint['id']}", json={"goal": "Noch geheimer", "version": 1}
    )
    same = await desk.moderator.patch(
        f"/api/sprints/{sprint['id']}", json={"goal": "Noch geheimer", "version": 2}
    )
    assert same.json()["version"] == 2  # nothing changed: no new version, no event
    sprint = (await start(desk.moderator, r.json())).json()
    await close(desk.moderator, sprint, "backlog")
    events = list(
        await session.scalars(
            select(EventOutbox).where(EventOutbox.type.like("sprint.%")).order_by(EventOutbox.id)
        )
    )
    assert [e.type for e in events] == [
        "sprint.created",
        "sprint.updated",
        "sprint.started",
        "sprint.closed",
    ]
    assert all(str(e.subject_id) == sprint["id"] and e.subject_type == "sprint" for e in events)
    assert all(str(e.space_id) == desk.space_id for e in events)
    assert events[1].payload == {"sprint_id": sprint["id"], "fields": ["goal"]}
    assert "geheim" not in json.dumps([e.payload for e in events]).lower()
    audited = await session.execute(
        select(AuditLog.action, AuditLog.details)
        .where(AuditLog.target_type == "sprint")
        .order_by(AuditLog.id)
    )
    rows = list(audited)
    assert [action for action, _ in rows] == ["sprint.created", "sprint.started", "sprint.closed"]
    assert rows[2][1] == {
        "space_id": desk.space_id,
        "move_open_to": "backlog",
        "planned": 0,
        "done": 0,
        "carried": 0,
    }
