"""Plan M6 task 9: `propose_skill` (level 2) proposes a new skill or a change to one of
the run's skills; whoever may manage skills in the scope accepts or rejects it. An
accepted proposal makes the skill version with the agent as author; a skill that
moved on answers 409 with both texts until the moderator accepts the final text."""

import uuid
from typing import Any

from sqlalchemy import select

from app.core.errors import Forbidden
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.toolbox import skill_tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.skills.models import SkillVersion
from app.modules.skills.proposal_decisions import FinalText, SkillProposalDecisions
from app.modules.skills.proposal_models import SkillProposal
from app.modules.skills.proposals import SkillProposalService
from tests.factories_skills import Lab, made
from tests.factories_tools import tool_context
from tests.test_access import actor_of

PROPOSALS = "/api/skill-proposals"


async def _assign(lab: Lab, *skill_ids: str) -> None:
    url = f"/api/agents/{lab.bench.agent.id}/skills"
    version = (await lab.admin.get(url)).json()["version"]
    r = await lab.admin.put(url, json={"skill_ids": list(skill_ids), "version": version})
    assert r.status_code == 200, r.text


async def propose(lab: Lab, **args: Any) -> str:
    """The tool, called in Alice's DM with the agent; the new proposal's id."""
    ctx = await tool_context(lab.bench)
    body = {"description": "Neu beschrieben.", "content": "# Neu\n", "reason": "Fehlt", **args}
    result = await skill_tools.propose_skill(ctx, skill_tools.ProposeSkillArgs(**body))
    assert "Skill proposal id=" in result.text, result.text
    return result.text.split("id=")[1].split(" ")[0].rstrip(";")


async def _ready(lab: Lab) -> None:
    await lab.bench.join(lab.space, SpaceRole.EDITOR)


def test_propose_skill_is_a_proposing_tool_of_level_2() -> None:
    spec = CATALOG["propose_skill"]
    assert (spec.level, spec.effect.value) == (2, "propose")


async def test_a_new_skill_proposed_in_a_space_is_accepted_with_the_agent_as_author(
    lab: Lab,
) -> None:
    await _ready(lab)
    proposal_id = await propose(lab, kind="new", name="labor-regeln", space_id=lab.space_id)
    shown = (await lab.alice.get(f"{PROPOSALS}/{proposal_id}")).json()
    assert shown["state"] == "open" and shown["kind"] == "new"
    assert shown["name"] == "labor-regeln" and shown["space_id"] == lab.space_id
    assert shown["author"] == {"type": "agent", "id": str(lab.bench.agent.id), "name": "Ava"}
    assert shown["proposed"] == {"description": "Neu beschrieben.", "content": "# Neu\n"}
    assert shown["current"] is None and shown["outdated"] is False
    assert shown["run_id"] is not None and shown["reason"] == "Fehlt"
    r = await lab.alice.post(f"{PROPOSALS}/{proposal_id}/accept", json={"version": 1})
    assert r.status_code == 200, r.text
    decided = r.json()
    assert decided["state"] == "accepted" and decided["result_number"] == 1
    assert decided["decided_by"]["id"] == lab.bench.people.id("alice")
    skill = (await lab.alice.get(f"/api/skills/{decided['skill_id']}")).json()
    assert skill["name"] == "labor-regeln" and skill["space_id"] == lab.space_id
    assert skill["author"]["type"] == "agent" and skill["content"] == "# Neu\n"
    version = (await lab.alice.get(f"/api/skills/{skill['id']}/versions/1")).json()
    assert version["author"] == {"type": "agent", "id": str(lab.bench.agent.id), "name": "Ava"}
    again = await lab.alice.post(f"{PROPOSALS}/{proposal_id}/accept", json={"version": 2})
    assert again.json()["error"]["code"] == "skill_proposal.not_open"


async def test_a_change_to_a_skill_that_moved_on_answers_both_texts(lab: Lab) -> None:
    await _ready(lab)
    skill = await made(lab.alice, space_id=lab.space_id, name="labor", content="# Alt\n")
    await _assign(lab, skill["id"])
    proposal_id = await propose(lab, kind="change", name="labor", content="# Agent\n")
    shown = (await lab.alice.get(f"{PROPOSALS}/{proposal_id}")).json()
    assert (shown["skill_id"], shown["name"], shown["base_number"]) == (skill["id"], "labor", 1)
    assert shown["current"]["content"] == "# Alt\n" and shown["outdated"] is False
    moved = await lab.alice.patch(
        f"/api/skills/{skill['id']}", json={"version": skill["version"], "content": "# Mensch\n"}
    )
    assert moved.status_code == 200, moved.text
    r = await lab.alice.post(f"{PROPOSALS}/{proposal_id}/accept", json={"version": 1})
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "skill_proposal.base_outdated"
    assert error["details"]["current"]["content"] == "# Mensch\n"
    assert error["details"]["proposed"]["content"] == "# Agent\n"
    seen_version = error["details"]["skill_version"]
    assert (await lab.alice.get(f"{PROPOSALS}/{proposal_id}")).json()["outdated"] is True
    stale = await lab.alice.post(
        f"{PROPOSALS}/{proposal_id}/accept", json={"version": 1, "skill_version": seen_version - 1}
    )
    assert stale.json()["error"]["code"] == "skill_proposal.base_outdated"
    body = {"version": 1, "skill_version": seen_version, "content": "# Mensch und Agent\n"}
    r = await lab.alice.post(f"{PROPOSALS}/{proposal_id}/accept", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["result_number"] == 3
    version = (await lab.alice.get(f"/api/skills/{skill['id']}/versions/3")).json()
    assert version["content"] == "# Mensch und Agent\n"
    assert version["author"]["id"] == lab.bench.people.id("alice")  # her final text


async def test_an_accepted_change_as_proposed_is_the_agents_version(lab: Lab) -> None:
    await _ready(lab)
    skill = await made(lab.alice, space_id=lab.space_id, name="labor", content="# Alt\n")
    await _assign(lab, skill["id"])
    proposal_id = await propose(lab, kind="change", name="labor", content="# Agent\n")
    r = await lab.alice.post(f"{PROPOSALS}/{proposal_id}/accept", json={"version": 1})
    assert r.status_code == 200, r.text
    version = (await lab.alice.get(f"/api/skills/{skill['id']}/versions/2")).json()
    assert version["author"]["type"] == "agent" and version["content"] == "# Agent\n"


async def test_rejecting_keeps_the_skill_and_records_why(lab: Lab) -> None:
    await _ready(lab)
    proposal_id = await propose(lab, kind="new", name="labor-x", space_id=lab.space_id)
    late = await lab.alice.post(f"{PROPOSALS}/{proposal_id}/reject", json={"version": 7})
    assert late.json()["error"]["code"] == "skill_proposal.version_conflict"
    r = await lab.alice.post(
        f"{PROPOSALS}/{proposal_id}/reject", json={"version": 1, "reason": "Gibt es schon"}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["state"], r.json()["decision_reason"]) == ("rejected", "Gibt es schon")
    assert r.json()["skill_id"] is None
    assert (await lab.alice.get("/api/skills", params={"q": "labor-x"})).json()["items"] == []


async def test_only_who_manages_the_scope_decides(lab: Lab) -> None:
    await _ready(lab)
    in_space = await propose(lab, kind="new", name="labor-y", space_id=lab.space_id)
    org_wide = await propose(lab, kind="new", name="fuer-alle")
    # Bob (viewer) sees neither; Alice (moderator of Labor, no skill.manage) not the
    # organisation-wide one; the admin decides both.
    for who, proposal_id in (("bob", in_space), ("bob", org_wide), ("alice", org_wide)):
        r = await getattr(lab, who).post(f"{PROPOSALS}/{proposal_id}/accept", json={"version": 1})
        assert r.status_code == 404 and r.json()["error"]["code"] == "skill_proposal.not_found"
    r = await lab.admin.post(f"{PROPOSALS}/{org_wide}/accept", json={"version": 1})
    assert r.status_code == 200, r.text
    skill = (await lab.admin.get(f"/api/skills/{r.json()['skill_id']}")).json()
    assert skill["space_id"] is None and skill["name"] == "fuer-alle"


async def test_a_run_never_decides(lab: Lab) -> None:
    await lab.bench.join(lab.space, SpaceRole.MODERATOR)  # the run sees it as a moderator
    proposal_id = uuid.UUID(await propose(lab, kind="new", name="labor-z", space_id=lab.space_id))
    ctx = await tool_context(lab.bench)  # Alice, moderator, but as a run
    decisions = SkillProposalDecisions(lab.bench.session)
    try:
        await decisions.accept(ctx.actor, proposal_id, 1, FinalText())
    except Forbidden as exc:
        assert exc.code == "auth.permission_denied"
    else:
        raise AssertionError("a run decided")


async def test_what_a_proposal_needs(lab: Lab) -> None:
    await _ready(lab)
    ctx = await tool_context(lab.bench)
    text = {"description": "d", "content": "c", "reason": "r"}

    async def tool(**args: Any) -> str:
        found = await skill_tools.propose_skill(ctx, skill_tools.ProposeSkillArgs(**text, **args))
        return found.text

    assert await tool(kind="change", name="unbekannt") == NOT_FOUND
    taken = await made(lab.alice, space_id=lab.space_id, name="vergeben")
    await _assign(lab, taken["id"])
    assert "skill.name_taken" in await tool(kind="new", name="vergeben", space_id=lab.space_id)
    assert "skill.name_invalid" in await tool(kind="new", name="Kein Name", space_id=lab.space_id)
    same = {"description": taken["description"], "content": "# PDF\n", "reason": "r"}
    result = await skill_tools.propose_skill(
        ctx, skill_tools.ProposeSkillArgs(kind="change", name="vergeben", **same)
    )
    assert "skill_proposal.no_change" in result.text
    assert (await lab.bench.session.scalars(select(SkillProposal))).all() == []


async def test_a_person_author_proposes_for_themselves_only(lab: Lab) -> None:
    alice = await actor_of(lab.bench.session, lab.bench.people.users["alice"])
    service = SkillProposalService(lab.bench.session)
    bob = Principal.user(lab.bench.people.users["bob"].id)
    try:
        await service.propose_new(alice, None, "x-y", "d", "c", "r", author=bob)
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "code", None) == "skill_proposal.bad_author"
    else:
        raise AssertionError("someone else's name was taken")
    made_by_her = await service.propose_new(
        alice, None, "x-y", "d", "c", "r", author=alice.principal
    )
    assert made_by_her.author_id == alice.principal.id and made_by_her.run_id is None


async def test_versions_record_their_authors(lab: Lab) -> None:
    await _ready(lab)
    proposal_id = await propose(lab, kind="new", name="labor-v", space_id=lab.space_id)
    await lab.alice.post(f"{PROPOSALS}/{proposal_id}/accept", json={"version": 1})
    rows = (await lab.bench.session.scalars(select(SkillVersion))).all()
    assert [(v.number, v.author_type) for v in rows] == [(1, "agent")]
