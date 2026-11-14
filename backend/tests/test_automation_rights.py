"""Whose rights an automation's run has (plan M7 decision 2): its owner's ∩ the
agent's ∩ the audience of its place, as in M6. An owner who no longer may run it
(deactivated, out of its space) pauses it, with an activity entry for the agent's
responsible person and the space's managers (in a DM only the responsible person);
someone who could make it may take it over. Approvals go to the owner."""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.core.errors import Conflict, Forbidden, NotFound
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import RunState, StopReason
from app.modules.automations.firing import fire_next
from app.modules.automations.models import AutomationState, PausedReason
from app.modules.automations.takeover import take_over
from app.modules.proposals.models import PageProposal
from app.modules.spaces.repository import SpaceRepository
from tests.factories_automations import T0, fire, firings, notified, placed, reload, runs_of
from tests.factories_tools import call
from tests.factories_wiki import new_page
from tests.factories_writing import Work, events
from tests.test_access import actor_of
from tests.test_approvals import NEW, confirm, decide

SECRET = "GEHEIMER-ENTWURF-77"


async def _channel(work: Work) -> uuid.UUID:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "bericht"})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


async def _reads_the_draft(work: Work, place: object, draft: dict[str, Any], at: Any) -> bool:
    bench = work.bench
    await placed(bench, place, due=at, instruction="Lies den Entwurf", cron=None)  # once
    bench.stub.state.replies.extend([call("read_page", page_id=draft["id"]), {"content": "ok"}])
    await fire(bench, at)
    before = len(bench.stub.state.log)
    assert await bench.run_next() == StopReason.COMPLETED
    return any(SECRET in r.text for r in bench.stub.state.log[before:])


async def test_a_channel_run_reads_as_a_viewer_and_a_dm_run_as_its_owner(work: Work) -> None:
    """Alice (editor) sees the draft; a viewer of the space does not: her automation
    in the channel does not read it, her automation in her DM does."""
    draft = await new_page(work.admin, work.space.id, "Entwurf", content_md=SECRET)
    assert draft["status"] == "draft"
    assert not await _reads_the_draft(work, await _channel(work), draft, T0)
    assert await _reads_the_draft(work, work.bench.dm_id, draft, T0.replace(hour=10))


async def test_a_deactivated_owner_pauses_it_and_tells_the_responsible_person(
    work: Work,
) -> None:
    bench = work.bench
    automation = await placed(bench, bench.dm_id)
    bench.people.users["alice"].is_active = False
    await bench.session.flush()
    fired = await fire(bench)
    assert (fired.outcome, fired.paused, fired.run_id) == (None, PausedReason.OWNER, None)
    after = await reload(bench.session, automation.id)
    assert (after.state, after.paused_reason, after.next_due_at) == ("paused", "owner", T0)
    assert await runs_of(bench.session, automation.id) == []
    assert await firings(bench.session, automation.id) == []  # it keeps the term
    admin = bench.people.users["admin"]  # Ava's responsible person; a DM: nobody else
    assert await notified(bench.session, automation.id) == [(admin.id, "automation")]
    r = await bench.people.admin.get("/api/activity")
    (entry,) = [a for a in r.json()["items"] if a["reason"] == "automation"]
    assert entry["automation"] == {"id": str(automation.id), "paused_reason": "owner"}
    assert entry["author"]["type"] == "agent" and entry["author"]["name"] == "Ava"
    assert (entry["conversation"], entry["message_id"], entry["snippet"]) == (None, None, "")
    (event,) = await events(bench.session, "notification.created")
    assert set(event.payload) == {"notification_id", "conversation_id", "message_id", "user_id"}
    assert await fire_next(bench.session, T0.replace(hour=20)) is None  # paused


async def _lost_space(work: Work) -> uuid.UUID:
    """Alice's automation in the channel; Bob manages the space; Alice leaves it."""
    bench = work.bench
    automation = await placed(bench, await _channel(work))
    spaces = SpaceRepository(bench.session)
    bob, alice = bench.people.users["bob"], bench.people.users["alice"]
    await spaces.set_member(work.space.id, Principal.user(bob.id), SpaceRole.ADMIN)
    await spaces.remove_member(work.space.id, Principal.user(alice.id))
    fired = await fire(bench)
    assert fired.paused == PausedReason.OWNER
    return automation.id


async def test_an_owner_out_of_the_space_pauses_it_and_its_managers_learn(work: Work) -> None:
    bench = work.bench
    automation_id = await _lost_space(work)
    after = await reload(bench.session, automation_id)
    assert (after.state, after.paused_reason) == (AutomationState.PAUSED, PausedReason.OWNER)
    admin, bob = bench.people.users["admin"], bench.people.users["bob"]
    expected = sorted([(admin.id, "automation"), (bob.id, "automation")])
    assert await notified(bench.session, automation_id) == expected
    assert await runs_of(bench.session, automation_id) == []


async def test_who_could_make_it_takes_it_over_and_it_runs_as_theirs(work: Work) -> None:
    bench = work.bench
    automation_id = await _lost_space(work)
    paused = await reload(bench.session, automation_id)
    version = paused.version
    carol = await actor_of(bench.session, bench.people.users["carol"])  # not in the space
    with pytest.raises(Forbidden) as refused:
        await take_over(bench.session, carol, automation_id, version)
    assert refused.value.code == "automation.not_allowed"
    guest = await actor_of(bench.session, bench.people.users["gast"])  # no AI
    with pytest.raises(NotFound):
        await take_over(bench.session, guest, automation_id, version)
    bob = await actor_of(bench.session, bench.people.users["bob"])
    with pytest.raises(Conflict) as stale:
        await take_over(bench.session, bob, automation_id, version - 1)
    assert stale.value.code == "automation.version_conflict"
    unchanged = await reload(bench.session, automation_id)
    assert (unchanged.owner_user_id, unchanged.version) == (bench.people.users["alice"].id, version)
    taken = await take_over(bench.session, bob, automation_id, version)
    assert (taken.owner_user_id, taken.state, taken.paused_reason) == (
        bob.principal.id,
        AutomationState.ACTIVE,
        None,
    )
    assert taken.version == version + 1
    fired = await fire(bench)  # the kept term fires once
    run = await bench.run_of(fired.run_id)
    assert (run.user_id, run.state) == (bob.principal.id, RunState.QUEUED)


async def test_an_approval_goes_to_the_owner_and_her_decision_resumes_the_run(
    work: Work,
) -> None:
    bench = work.bench
    page_id = await work.page()
    await confirm(work, "propose_page_change")
    args = {"page_id": page_id, "content_md": NEW, "reason": "Klarer"}
    bench.stub.state.replies.extend([call("propose_page_change", **args), {"content": "Fertig"}])
    automation = await placed(bench, bench.dm_id)
    fired = await fire(bench)
    assert await bench.run_next() is None  # waits
    assert (await bench.run_of(fired.run_id)).state == RunState.WAITING
    r = await bench.people.alice.get("/api/approvals", params={"state": "pending"})
    (approval,) = r.json()["items"]
    activity = (await bench.people.alice.get("/api/activity")).json()["items"]
    assert [a["reason"] for a in activity] == ["approval"]
    theirs = await bench.people.admin.get("/api/approvals", params={"state": "pending"})
    assert theirs.json()["items"] == []
    assert (await decide(work, approval, "approve", who="admin")).status_code == 403
    assert (await decide(work, approval, "approve")).status_code == 200
    assert await bench.run_next() == StopReason.COMPLETED
    proposals = (await bench.session.scalars(select(PageProposal))).all()
    assert len(proposals) == 1
    [run] = await runs_of(bench.session, automation.id)
    assert run.stop_reason == StopReason.COMPLETED
    for event in await events(bench.session, "message.created"):
        assert "Summarise" not in json.dumps(event.payload)
