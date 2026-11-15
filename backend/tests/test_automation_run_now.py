"""Running an automation now and taking it over through the API (plan M7 decisions 2
and 14): "run now" is one term out of turn through the checks of a due term (its
owner only; a second while the first runs is `skipped_busy`, not a second run; not
for event rules); a take-over makes someone who could make it its owner."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.audit.models import AuditLog
from app.modules.automations.firing import fire_next
from app.modules.automations.models import AutomationFiring
from app.modules.spaces.repository import SpaceRepository
from tests.factories_automations import runs_of
from tests.factories_writing import Work
from tests.test_automation_api import BASE, DAILY, NOW, body, channel, clock, make, refused
from tests.test_automation_changes import in_channel, post

__all__ = ["clock"]


async def test_run_now_fires_one_term_and_a_second_meanwhile_is_skipped(work: Work) -> None:
    bench = work.bench
    made = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    r = await bench.people.alice.post(f"{BASE}/{made['id']}/run")
    assert r.status_code == 200, r.text
    first = r.json()["last_run"]
    assert first["outcome"] == "started" and first["run_state"] == "queued"
    assert r.json()["next_due_at"] == made["next_due_at"]  # its schedule stays
    assert r.json()["version"] == made["version"]
    again = await bench.people.alice.post(f"{BASE}/{made['id']}/run")
    assert again.status_code == 200, again.text
    assert (again.json()["last_run"]["outcome"], again.json()["last_run"]["run_id"]) == (
        "skipped_busy",
        None,
    )
    runs = await runs_of(bench.session, uuid.UUID(made["id"]))
    assert [str(r.id) for r in runs] == [first["run_id"]]
    stmt = select(AutomationFiring.outcome).where(
        AutomationFiring.automation_id == uuid.UUID(made["id"])
    )
    assert sorted((await bench.session.scalars(stmt)).all()) == ["skipped_busy", "started"]


async def test_run_now_is_its_owners_and_not_for_event_rules_or_paused_ones(work: Work) -> None:
    made = await in_channel(work)
    bob, alice = work.bench.people.bob, work.bench.people.alice  # bob manages the space
    refused(await bob.post(f"{BASE}/{made['id']}/run"), 403, "automation.not_allowed")
    paused = (await post(alice, made, "pause")).json()
    refused(await alice.post(f"{BASE}/{paused['id']}/run"), 409, "automation.not_active")
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(work.bench.people.users["alice"].id), SpaceRole.ADMIN
    )
    place = {"type": "channel", "conversation_id": await channel(work)}
    rule = await make(alice, body(work, place, {"kind": "event", "event_type": "page.published"}))
    refused(await alice.post(f"{BASE}/{rule['id']}/run"), 409, "automation.not_runnable")
    refused(
        await work.bench.people.carol.post(f"{BASE}/{made['id']}/run"), 404, "automation.not_found"
    )


async def test_run_now_pauses_it_when_its_owner_may_no_longer_run_it(work: Work) -> None:
    """Alice left the space of its channel: she still sees her automation, but the
    term's checks pause it instead of running it."""
    made = await in_channel(work)
    alice = work.bench.people.users["alice"]
    await SpaceRepository(work.bench.session).remove_member(work.space.id, Principal.user(alice.id))
    r = await work.bench.people.alice.post(f"{BASE}/{made['id']}/run")
    assert r.status_code == 200, r.text
    assert (r.json()["state"], r.json()["paused_reason"], r.json()["last_run"]) == (
        "paused",
        "owner",
        None,
    )
    assert await runs_of(work.bench.session, uuid.UUID(made["id"])) == []


async def test_a_manager_takes_it_over_after_its_owner_left(work: Work) -> None:
    made = await in_channel(work)
    bench = work.bench
    alice = bench.people.users["alice"]
    await SpaceRepository(bench.session).remove_member(work.space.id, Principal.user(alice.id))
    fired = await fire_next(bench.session, NOW + timedelta(days=1))
    assert fired is not None and fired.paused == "owner"
    current = (await bench.people.bob.get(f"{BASE}/{made['id']}")).json()
    refused(
        await post(bench.people.bob, current, "take-over", 1), 409, "automation.version_conflict"
    )
    refused(await post(bench.people.carol, current, "take-over"), 404, "automation.not_found")
    r = await post(bench.people.bob, current, "take-over")
    assert r.status_code == 200, r.text
    taken = r.json()
    assert taken["owner"]["id"] == bench.people.id("bob")
    assert (taken["state"], taken["paused_reason"], taken["abilities"]["edit"]) == (
        "active",
        None,
        True,
    )
    assert taken["abilities"]["take_over"] is False
    stmt = select(AuditLog.details).where(AuditLog.action == "automation.taken_over")
    (details,) = (await bench.session.scalars(stmt)).all()
    assert details == {"from": str(alice.id), "to": bench.people.id("bob")}


async def test_who_sees_it_but_could_not_make_it_may_not_take_it_over(work: Work) -> None:
    """Carol, the agent's responsible person, sees it but may not post in the space."""
    made = await in_channel(work)
    work.bench.agent.responsible_user_id = work.bench.people.users["carol"].id
    await work.bench.session.flush()
    r = await post(work.bench.people.carol, made, "take-over")
    refused(r, 403, "automation.not_allowed")
