"""Review of M10 task 4 (invitations and answers): one test per finding R4-n of
`.superpowers/sdd/m10/review-task-4.md`. Each fails until its finding is fixed."""

import gc
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import launch
from app.core.config import Settings
from tests.factories import MakeUser
from tests.factories_agents import Bench
from tests.factories_calendar import new_calendar, new_event, window
from tests.factories_invitations import (
    SPAN,
    Team,
    answer,
    calendar_handlers,
    invite,
    notes,
    person,
    team,
)
from tests.factories_spaces import MakeSpace
from tests.test_agents import body as agent_body

SECOND = "2026-11-30T10:00:00"  # the second Monday of the weekly series, its wall time


async def _series(t: Team, *invited: dict[str, Any]) -> dict[str, Any]:
    made = await new_event(
        t.organiser_client, t.calendar["id"], title="Jour fixe", rrule="FREQ=WEEKLY;COUNT=4"
    )
    return await invite(t.organiser_client, made, *invited) if invited else made


async def _patch(client: AsyncClient, event: dict[str, Any], **body: Any) -> dict[str, Any]:
    params = {k: body.pop(k) for k in ("scope", "occurrence") if k in body}
    version = (await client.get(f"/api/events/{event['id']}")).json()["version"]
    r = await client.patch(
        f"/api/events/{event['id']}", params=params, json={"version": version, **body}
    )
    assert r.status_code == 200, r.text
    changed: dict[str, Any] = r.json()["event"]
    return changed


async def _one_occurrence_guest(t: Team, session: AsyncSession) -> tuple[dict[str, Any], Any]:
    """A series whose second occurrence alone has a guest (the outsider), who accepted
    and read her invitation: (series, her notification)."""
    series = await _series(t)
    override = await _patch(
        t.organiser_client, series, scope="this", occurrence=SECOND, title="Mit Gast"
    )
    await invite(t.organiser_client, override, person(t.outsider))
    assert (await answer(t.outsider_client, override["id"], "accepted")).status_code == 200
    await calendar_handlers(session)
    (first,) = await notes(session, t.outsider)
    assert len(await window(t.outsider_client, *SPAN)) == 1
    return series, first


async def test_r4_1_someone_invited_to_one_occurrence_hears_when_the_series_is_deleted(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """Decision 7: `invitation` when an event is called off. Deleting the series makes
    its overrides tombstones; who is invited to one of them alone is told nothing."""
    t = await team(make_client, make_user, make_space)
    series, first = await _one_occurrence_guest(t, session)
    version = (await t.organiser_client.get(f"/api/events/{series['id']}")).json()["version"]
    gone = await t.organiser_client.delete(
        f"/api/events/{series['id']}", params={"version": version}
    )
    assert gone.status_code == 204, gone.text
    assert await window(t.outsider_client, *SPAN) == []  # her occurrence went
    await calendar_handlers(session)
    (told,) = await notes(session, t.outsider)
    assert told.id != first.id  # told again: it was deleted


async def test_r4_1_someone_invited_to_one_occurrence_hears_when_the_series_is_cancelled(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """Cancelling a series reaches every override (`series_reach.EVERYWHERE`); the
    people of those overrides are told nothing."""
    t = await team(make_client, make_user, make_space)
    series, first = await _one_occurrence_guest(t, session)
    await _patch(t.organiser_client, series, status="cancelled")
    (shown,) = await window(t.outsider_client, *SPAN)
    assert shown["status"] == "cancelled"  # her occurrence was called off
    await calendar_handlers(session)
    (told,) = await notes(session, t.outsider)
    assert told.id != first.id  # told again: it was cancelled


async def test_r4_2_a_redelivered_invitation_leaves_a_read_notification_read(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """Plan task 4: delivering the event twice makes one notification; handlers are
    idempotent (CLAUDE.md). A second delivery must not bring a read one back."""
    t = await team(make_client, make_user, make_space)
    event = await new_event(t.organiser_client, t.calendar["id"])
    await invite(t.organiser_client, event, person(t.outsider))
    await calendar_handlers(session)
    (first,) = await notes(session, t.outsider)
    assert (await t.outsider_client.post(f"/api/activity/{first.id}/read")).status_code == 204
    assert (await t.outsider_client.get("/api/activity/count")).json()["unread"] == 0
    await calendar_handlers(session, again=True)  # the worker had the same event again
    (after,) = await notes(session, t.outsider)
    assert after.id == first.id
    assert after.read_at is not None
    assert (await t.outsider_client.get("/api/activity/count")).json()["unread"] == 0


async def test_r4_3_deleting_one_occurrence_tells_the_attendees(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """Decision 7: `invitation` also when an event is called off. Cancelling one
    occurrence (`status`, `scope=this`) tells; deleting it (`scope=this`) is silent."""
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.outsider))
    await calendar_handlers(session)
    (first,) = await notes(session, t.outsider)
    gone = await t.organiser_client.delete(
        f"/api/events/{series['id']}",
        params={"version": series["version"], "scope": "this", "occurrence": SECOND},
    )
    assert gone.status_code == 204, gone.text
    assert len(await window(t.outsider_client, *SPAN)) == 3
    await calendar_handlers(session)
    told = await notes(session, t.outsider)
    assert [n.id for n in told] != [first.id]  # she hears that an occurrence went


async def test_r4_4_deleting_an_invited_agent_leaves_no_nameless_attendee(
    bench: Bench, make_space: MakeSpace
) -> None:
    """Attendee rows name a principal without a foreign key. An agent that never
    talked can be deleted (`AgentRepository.in_use` knows nothing of invitations):
    its attendee row stays, accepted, with no name, on every event it was invited to."""
    admin, alice = bench.people.admin, bench.people.alice
    space = await make_space("team", members=[(bench.people.users["alice"], "moderator")])
    calendar = await new_calendar(alice, space.id, "Team")
    event = await new_event(alice, calendar["id"])
    made = await admin.post("/api/agents", json=agent_body(bench, status="active"))
    assert made.status_code == 201, made.text
    agent = made.json()
    await invite(alice, event, {"type": "agent", "id": agent["id"]})
    gone = await admin.delete(f"/api/agents/{agent['id']}?version={agent['version']}")
    if gone.status_code == 409:
        assert gone.json()["error"]["code"] == "agent.in_use"  # one fix: it stays
        return
    assert gone.status_code == 204, gone.text
    r = await alice.get(f"/api/events/{event['id']}/attendees")
    assert r.json()["items"] == []  # the other fix: its invitations go with it


async def test_r4_5_serving_in_a_test_does_not_freeze_the_test_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`launch.serve` now freezes the heap of the process it runs in. Three tests
    (`test_worker_role.py` twice, `test_spool_dir.py`) call it with `run_servers`
    faked and nothing else: the whole pytest process is frozen from there on, so
    whatever cyclic garbage exists then is never freed and later tests run with a
    collector that differs from every other session's. This is one of those calls."""

    async def fake_run_servers(servers: object) -> int:
        return 0

    monkeypatch.setattr(launch, "run_servers", fake_run_servers)
    gc.unfreeze()  # whatever an earlier test of the session left frozen
    try:
        assert await launch.serve(Settings(role="worker", internal_port=9191)) == 0
        assert gc.get_freeze_count() == 0
    finally:
        gc.unfreeze()
