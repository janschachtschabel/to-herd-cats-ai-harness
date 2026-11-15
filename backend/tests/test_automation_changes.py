"""Changing an automation (plan M7 decisions 12 to 14): only its owner edits it (the
kind stays, a new schedule computes its next term anew); its owner, the managers of
its place's space and `agent.manage` pause, resume and delete it. Every change names
the version read (409 otherwise) and is audited with ids only. A deleted automation
is gone for the API, but its runs and their journal stay as history; a run open when
it is deleted ends as it would have."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.run_models import Run, StopReason
from app.modules.audit.models import AuditLog
from app.modules.automations.firing import fire_next
from app.modules.automations.models import Automation
from app.modules.spaces.repository import SpaceRepository
from tests.factories_automations import reload
from tests.factories_writing import Work
from tests.test_automation_api import BASE, DAILY, NOW, SECRET, body, channel, clock, make, refused

__all__ = ["clock"]


async def in_channel(work: Work) -> dict[str, Any]:
    """Alice's automation in a channel of the space, Bob a manager of the space."""
    bob = work.bench.people.users["bob"]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(bob.id), SpaceRole.ADMIN
    )
    place = {"type": "channel", "conversation_id": await channel(work)}
    return await make(work.bench.people.alice, body(work, place, DAILY))


async def post(client: Any, made: dict[str, Any], action: str, version: int | None = None) -> Any:
    return await client.post(
        f"{BASE}/{made['id']}/{action}", json={"version": version or made["version"]}
    )


async def test_its_owner_changes_its_words_and_its_schedule(work: Work) -> None:
    made = await in_channel(work)
    alice, bob = work.bench.people.alice, work.bench.people.bob
    hourly = {"kind": "recurring", "cron": "30 * * * *", "time_zone": "UTC"}
    change = {"version": 1, "instruction": "Neu", "schedule": hourly}
    refused(await bob.patch(f"{BASE}/{made['id']}", json=change), 403, "automation.not_allowed")
    r = await alice.patch(f"{BASE}/{made['id']}", json=change)
    assert r.status_code == 200, r.text
    changed = r.json()
    assert (changed["version"], changed["instruction"], changed["cron"]) == (2, "Neu", "30 * * * *")
    assert datetime.fromisoformat(changed["next_due_at"]) == NOW + timedelta(minutes=30)
    stale = await alice.patch(f"{BASE}/{made['id']}", json={"version": 1, "instruction": "x"})
    refused(stale, 409, "automation.version_conflict")
    assert stale.json()["error"]["details"]["current_version"] == 2
    other_kind = {"version": 2, "schedule": {"kind": "event", "event_type": "page.published"}}
    refused(
        await alice.patch(f"{BASE}/{made['id']}", json=other_kind), 422, "automation.kind_immutable"
    )
    session = work.bench.session
    stmt = select(AuditLog).where(AuditLog.target_id == uuid.UUID(made["id"]))
    entries = {a.action: a.details for a in (await session.scalars(stmt)).all()}
    assert entries["automation.updated"] == {"fields": ["instruction", "schedule"]}
    assert SECRET not in str(entries) and "Neu" not in str(entries)


async def test_a_done_once_given_a_new_instant_is_active_again(work: Work) -> None:
    alice = work.bench.people.alice
    at = NOW + timedelta(hours=1)
    made = await make(alice, body(work, {"type": "dm"}, {"kind": "once", "at": at.isoformat()}))
    await fire_next(work.bench.session, at)
    assert (await reload(work.bench.session, uuid.UUID(made["id"]))).state == "done"
    later = {"kind": "once", "at": (NOW + timedelta(days=1)).isoformat()}
    version = (await alice.get(f"{BASE}/{made['id']}")).json()["version"]
    r = await alice.patch(f"{BASE}/{made['id']}", json={"version": version, "schedule": later})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "active"
    assert datetime.fromisoformat(r.json()["next_due_at"]) == NOW + timedelta(days=1)


async def test_a_manager_pauses_and_resumes_it_and_the_count_starts_anew(work: Work) -> None:
    made = await in_channel(work)
    bob = work.bench.people.bob
    r = await post(bob, made, "pause")
    assert r.status_code == 200, r.text
    paused = r.json()
    assert (paused["state"], paused["paused_reason"], paused["version"]) == ("paused", "manual", 2)
    refused(await post(bob, paused, "pause"), 409, "automation.not_active")
    row = await work.bench.session.get(Automation, uuid.UUID(made["id"]))
    assert row is not None
    row.failures = 2
    await work.bench.session.flush()
    refused(await post(bob, made, "resume"), 409, "automation.version_conflict")
    r = await post(bob, paused, "resume")
    assert r.status_code == 200, r.text
    resumed = r.json()
    assert (resumed["state"], resumed["paused_reason"], resumed["version"]) == ("active", None, 3)
    assert (await reload(work.bench.session, row.id)).failures == 0
    refused(await post(bob, resumed, "resume"), 409, "automation.not_paused")


async def test_resuming_is_refused_while_its_owner_may_not_run_it(work: Work) -> None:
    """Paused because Alice left the space: resuming would only pause it again; one
    who could make it takes it over instead."""
    made = await in_channel(work)
    alice = work.bench.people.users["alice"]
    await SpaceRepository(work.bench.session).remove_member(work.space.id, Principal.user(alice.id))
    fired = await fire_next(work.bench.session, NOW + timedelta(days=1))
    assert fired is not None and fired.paused == "owner"
    current = (await work.bench.people.bob.get(f"{BASE}/{made['id']}")).json()
    abilities = current["abilities"]
    assert (abilities["pause"], abilities["resume"], abilities["take_over"]) == (False, False, True)
    refused(await post(work.bench.people.bob, current, "resume"), 409, "automation.owner_unable")


async def test_deleting_keeps_its_runs_as_history_and_hides_it(work: Work) -> None:
    made = await in_channel(work)
    bench = work.bench
    fired = await fire_next(bench.session, NOW + timedelta(days=1))
    assert fired is not None and fired.run_id is not None
    refused(
        await bench.people.bob.delete(f"{BASE}/{made['id']}?version=9"),
        409,
        "automation.version_conflict",
    )
    carol = bench.people.carol  # sees nothing of it
    refused(await carol.delete(f"{BASE}/{made['id']}?version=1"), 404, "automation.not_found")
    r = await bench.people.bob.delete(f"{BASE}/{made['id']}?version=1")
    assert r.status_code == 204, r.text
    refused(await bench.people.alice.get(f"{BASE}/{made['id']}"), 404, "automation.not_found")
    assert (await bench.people.alice.get(BASE)).json()["items"] == []
    run = await bench.run_of(fired.run_id)
    assert run.automation_id == uuid.UUID(made["id"])
    assert await fire_next(bench.session, NOW + timedelta(days=9)) is None  # never due again
    stmt = select(AuditLog.action).where(AuditLog.target_id == uuid.UUID(made["id"]))
    assert "automation.deleted" in (await bench.session.scalars(stmt)).all()


async def test_a_run_open_when_it_is_deleted_ends_as_it_would_have(work: Work) -> None:
    bench = work.bench
    made = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    fired = await fire_next(bench.session, NOW + timedelta(days=1))
    assert fired is not None and fired.run_id is not None
    r = await bench.people.alice.delete(f"{BASE}/{made['id']}?version=1")
    assert r.status_code == 204, r.text
    bench.stub.state.replies.append({"content": "Erledigt."})
    assert await bench.run_next() == StopReason.COMPLETED
    after = await reload(bench.session, uuid.UUID(made["id"]))
    assert (after.state, after.paused_reason) == ("deleted", None)
    run = await bench.session.get(Run, fired.run_id)
    assert run is not None and run.stop_reason == StopReason.COMPLETED
    answers = [m for m in await bench.messages() if m["body_md"] == "Erledigt."]
    assert len(answers) == 1


async def test_who_only_sees_it_may_not_control_it(work: Work) -> None:
    """The agent's responsible person sees it (the admin here is also `agent.manage`,
    so Carol becomes the responsible person); she may neither pause nor change it."""
    made = await make(work.bench.people.alice, body(work, {"type": "dm"}, DAILY))
    carol = work.bench.people.users["carol"]
    work.bench.agent.responsible_user_id = carol.id
    await work.bench.session.flush()
    client = work.bench.people.carol
    assert (await client.get(f"{BASE}/{made['id']}")).status_code == 200
    refused(await post(client, made, "pause"), 403, "automation.not_allowed")
    refused(await client.delete(f"{BASE}/{made['id']}?version=1"), 403, "automation.not_allowed")


async def test_an_entry_about_a_deleted_automation_is_gone(work: Work) -> None:
    made = await in_channel(work)
    alice = work.bench.people.users["alice"]
    await SpaceRepository(work.bench.session).remove_member(work.space.id, Principal.user(alice.id))
    await fire_next(work.bench.session, NOW + timedelta(days=1))  # paused: `owner`
    bob = work.bench.people.bob  # a manager of the space: told of it

    async def entries() -> list[Any]:
        r = await bob.get("/api/activity")
        return [a for a in r.json()["items"] if a["reason"] == "automation"]

    assert len(await entries()) == 1
    version = (await bob.get(f"{BASE}/{made['id']}")).json()["version"]
    assert (await bob.delete(f"{BASE}/{made['id']}?version={version}")).status_code == 204
    assert await entries() == []
    assert (await bob.get("/api/activity/count")).json()["open"] == 0
