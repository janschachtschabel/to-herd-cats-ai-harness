"""Plan M6 task 9, review focus 1: skill proposals go only where the run may write and
only what that scope's audience may receive; they are hidden like nonexistent ones
from whoever may not decide them (the activity entries too, also after a role was
lost), and their events and live events carry ids only."""

import json
import uuid
from typing import Any

from sqlalchemy import select

from app.core.outbox import Event, EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.toolbox import skill_tools
from app.modules.agents.toolbox.writing import LEAKS
from app.modules.messaging.live_publish import of_event
from app.modules.skills.proposal_handlers import notify_on_skill_proposal
from app.modules.skills.proposals import SkillProposalService
from app.modules.spaces.models import SpaceKind
from app.modules.spaces.repository import SpaceRepository
from tests.factories_skills import Lab
from tests.factories_spaces import MakeSpace
from tests.factories_tools import tool_context
from tests.test_access import actor_of
from tests.test_skill_proposals import PROPOSALS, propose

SECRET = "GEHEIMNIS-7Q"
TEXT = {"description": f"d {SECRET}", "content": f"c {SECRET}", "reason": f"r {SECRET}"}


async def _handle(lab: Lab) -> None:
    rows = await lab.bench.session.scalars(
        select(EventOutbox)
        .where(
            EventOutbox.type.like("skill_proposal.%"), EventOutbox.subject_type == "skill_proposal"
        )
        .order_by(EventOutbox.id)
    )
    for row in rows.all():
        if row.type != "skill_proposal.changed":
            await notify_on_skill_proposal(lab.bench.session, Event.of(row))


async def _activity(lab: Lab, who: str) -> list[dict[str, Any]]:
    r = await getattr(lab, who).get("/api/activity")
    assert r.status_code == 200, r.text
    return [a for a in r.json()["items"] if a["reason"] == "skill_proposal"]


async def _role(lab: Lab, who: str, role: SpaceRole) -> None:
    user = lab.bench.people.users[who]
    await SpaceRepository(lab.bench.session).set_member(lab.space.id, Principal.user(user.id), role)


async def _tool(ctx: Any, **args: Any) -> str:
    result = await skill_tools.propose_skill(ctx, skill_tools.ProposeSkillArgs(**TEXT, **args))
    return result.text


async def test_proposals_go_only_where_the_run_may_write(lab: Lab, make_space: MakeSpace) -> None:
    await lab.bench.join(lab.space, SpaceRole.EDITOR)
    open_space = await make_space(SpaceKind.OPEN, "Offen")
    await lab.bench.join(open_space, SpaceRole.EDITOR)
    r = await lab.alice.post(f"/api/spaces/{lab.space_id}/channels", json={"name": "labor"})
    channel = await tool_context(lab.bench, r.json()["id"])  # writes in Labor only
    assert await _tool(channel, kind="new", name="x-offen", space_id=str(open_space.id)) == (
        "Not allowed here."
    )
    assert "Skill proposal id=" in await _tool(channel, kind="new", name="x", space_id=lab.space_id)
    bob = await tool_context(lab.bench, r.json()["id"], who="bob")  # Bob only views Labor
    assert await _tool(bob, kind="new", name="y", space_id=lab.space_id) == "Not allowed here."


async def test_nothing_read_elsewhere_goes_into_a_proposal(lab: Lab, make_space: MakeSpace) -> None:
    await lab.bench.join(lab.space, SpaceRole.EDITOR)
    other = await make_space(SpaceKind.TEAM, "Anderswo")
    open_space = await make_space(SpaceKind.OPEN, "Offen")
    ctx = await tool_context(lab.bench)
    ctx.reads.spaces.add(other.id)
    assert await _tool(ctx, kind="new", name="a", space_id=lab.space_id) == LEAKS
    assert await _tool(ctx, kind="new", name="b") == LEAKS  # organisation-wide
    fresh = await tool_context(lab.bench)
    fresh.reads.spaces.add(lab.space.id)  # a team space: not for the whole organisation
    assert await _tool(fresh, kind="new", name="c") == LEAKS
    assert "Skill proposal id=" in await _tool(fresh, kind="new", name="c", space_id=lab.space_id)
    opened = await tool_context(lab.bench)
    opened.reads.spaces.add(open_space.id)
    assert "Skill proposal id=" in await _tool(opened, kind="new", name="d")


async def test_an_unseen_proposal_answers_like_an_unknown_one(lab: Lab) -> None:
    await lab.bench.join(lab.space, SpaceRole.EDITOR)
    proposal_id = await propose(lab, kind="new", name="versteckt", space_id=lab.space_id)
    unknown = str(uuid.uuid4())
    for who in ("bob", "carol"):
        client = getattr(lab, who)
        for method, suffix, body in (
            ("GET", "", None),
            ("POST", "/accept", {"version": 1}),
            ("POST", "/reject", {"version": 1}),
        ):
            answers = []
            for pid in (proposal_id, unknown):
                r = await client.request(method, f"{PROPOSALS}/{pid}{suffix}", json=body)
                error = r.json()["error"]
                answers.append((r.status_code, error["code"], error["message"]))
            assert answers[0] == answers[1] == (404, "skill_proposal.not_found", answers[1][2])
        listed = (await client.get(PROPOSALS)).json()["items"]
        assert listed == []
    space = await lab.carol.get(PROPOSALS, params={"space_id": lab.space_id})
    assert space.json()["error"]["code"] == "space.not_found"
    mine = (await lab.alice.get(PROPOSALS, params={"space_id": lab.space_id})).json()
    assert [p["id"] for p in mine["items"]] == [proposal_id]
    assert (await lab.alice.get(PROPOSALS, params={"org_wide": True})).json()["items"] == []


async def test_activity_reaches_who_decides_and_leaves_with_the_role(lab: Lab) -> None:
    await lab.bench.join(lab.space, SpaceRole.EDITOR)
    proposal_id = await propose(lab, kind="new", name="labor-a", space_id=lab.space_id)
    await _handle(lab)
    await _handle(lab)  # delivered twice: one entry
    (entry,) = await _activity(lab, "alice")
    assert entry["skill_proposal"] == {"id": proposal_id, "space_id": lab.space_id}
    assert entry["conversation"] is None and entry["snippet"] == ""
    assert entry["author"] == {"type": "agent", "id": str(lab.bench.agent.id), "name": "Ava"}
    assert await _activity(lab, "bob") == [] and await _activity(lab, "admin") == []
    await _role(lab, "alice", SpaceRole.EDITOR)  # still edits pages there, decides nothing
    assert await _activity(lab, "alice") == []
    count = (await lab.alice.get("/api/activity/count")).json()
    assert count["open"] == 0


async def test_organisation_wide_proposals_reach_the_administrators(lab: Lab) -> None:
    await propose(lab, kind="new", name="fuer-alle")
    await _handle(lab)
    (entry,) = await _activity(lab, "admin")
    assert entry["skill_proposal"]["space_id"] is None
    assert await _activity(lab, "alice") == []


async def test_a_person_author_hears_of_the_decision(lab: Lab) -> None:
    alice = await actor_of(lab.bench.session, lab.bench.people.users["alice"])
    proposal = await SkillProposalService(lab.bench.session).propose_new(
        alice, None, "von-alice", "d", "c", "r", author=alice.principal
    )
    await _handle(lab)
    assert await _activity(lab, "alice") == []  # her own: no entry for making it
    r = await lab.admin.post(f"{PROPOSALS}/{proposal.id}/reject", json={"version": 1})
    assert r.status_code == 200, r.text
    await _handle(lab)
    (entry,) = await _activity(lab, "alice")
    assert entry["skill_proposal"]["id"] == str(proposal.id)
    shown = await lab.alice.get(f"{PROPOSALS}/{proposal.id}")
    assert shown.status_code == 200  # her own


async def test_events_and_live_events_carry_ids_only(lab: Lab) -> None:
    await lab.bench.join(lab.space, SpaceRole.EDITOR)
    ctx = await tool_context(lab.bench)
    made = await _tool(ctx, kind="new", name="geheim-name", space_id=lab.space_id)
    proposal_id = made.split("id=")[1].split(" ")[0].rstrip(";")
    await _handle(lab)
    r = await lab.alice.post(
        f"{PROPOSALS}/{proposal_id}/reject", json={"version": 1, "reason": SECRET}
    )
    assert r.status_code == 200
    await _handle(lab)
    rows = (await lab.bench.session.scalars(select(EventOutbox).order_by(EventOutbox.id))).all()
    for row in rows:
        assert SECRET not in json.dumps(row.payload) and "geheim-name" not in json.dumps(
            row.payload
        )
    live = [Event.of(r) for r in rows if r.type == "skill_proposal.changed"]
    alice = uuid.UUID(lab.bench.people.id("alice"))
    assert {e.payload["user_id"] for e in live} == {str(alice)}
    event = of_event(live[0])
    assert event is not None and event.user_id == alice
    assert event.proposal_id == uuid.UUID(proposal_id)
    frame = event.frame().decode()
    assert frame.startswith("event: skill_proposal.changed") and proposal_id in frame
    assert len(event.payload()) < 400


async def test_an_author_who_left_the_space_no_longer_sees_the_proposal(lab: Lab) -> None:
    bob = await actor_of(lab.bench.session, lab.bench.people.users["bob"])
    await _role(lab, "bob", SpaceRole.EDITOR)
    proposal = await SkillProposalService(lab.bench.session).propose_new(
        bob, lab.space.id, "von-bob", "d", "c", "r", author=bob.principal
    )
    assert (await lab.bob.get(f"{PROPOSALS}/{proposal.id}")).status_code == 200
    r = await lab.alice.post(f"{PROPOSALS}/{proposal.id}/reject", json={"version": 1})
    assert r.status_code == 200, r.text
    await _handle(lab)
    assert len(await _activity(lab, "bob")) == 1
    await SpaceRepository(lab.bench.session).remove_member(
        lab.space.id, Principal.user(lab.bench.people.users["bob"].id)
    )
    assert (await lab.bob.get(f"{PROPOSALS}/{proposal.id}")).status_code == 404
    assert await _activity(lab, "bob") == []
