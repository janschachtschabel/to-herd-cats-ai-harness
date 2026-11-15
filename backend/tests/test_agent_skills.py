"""An agent's skills (plan M6 task 9, decision 11): assigned by holders of
`agent.manage`, only skills that are organisation-wide or of a space the agent reads;
what a run may use is decided at use time (`skills_for_run`, `load_for_run`): the
skill is assigned and active, organisation-wide or in a space the run reads, and that
space's AI policy lets the run's connection receive it. Names that two usable skills
share are left out (the run could not tell them apart)."""

import uuid
from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import ReadScope
from app.core.principal import Principal
from app.modules.agents.actor import run_actor
from app.modules.ai.models import DataLocation
from app.modules.audit.models import AuditLog
from app.modules.skills.assignments import AgentSkills
from app.modules.skills.runs import load_for_run, skills_for_run
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from tests.factories_skills import SKILLS, Lab, made
from tests.factories_spaces import MakeSpace
from tests.test_access import actor_of

EXTERNAL = DataLocation("external")


def _url(lab: Lab) -> str:
    return f"/api/agents/{lab.bench.agent.id}/skills"


async def _assign(lab: Lab, *skill_ids: str, client: Any = None) -> Any:
    client = client or lab.admin
    version = (await client.get(_url(lab))).json()["version"]
    return await client.put(_url(lab), json={"skill_ids": list(skill_ids), "version": version})


async def _run_skills(lab: Lab, who: str = "alice", location: DataLocation = EXTERNAL) -> Any:
    session = lab.bench.session
    user = lab.bench.people.users[who]
    actor = await run_actor(session, user.org_id, user.id, lab.bench.agent.id)
    assert actor is not None
    return await skills_for_run(session, actor, lab.bench.agent.id, location)


async def _load(lab: Lab, name: str, who: str = "alice") -> Any:
    session = lab.bench.session
    user = lab.bench.people.users[who]
    actor = await run_actor(session, user.org_id, user.id, lab.bench.agent.id)
    assert actor is not None
    return await load_for_run(session, actor, lab.bench.agent.id, EXTERNAL, name)


async def test_a_manager_assigns_skills_the_agent_may_read(lab: Lab, session: AsyncSession) -> None:
    await lab.bench.join(lab.space)
    org = await made(lab.admin, name="org-skill")
    space = await made(lab.alice, space_id=lab.space_id, name="space-skill")
    before = (await lab.admin.get(_url(lab))).json()
    assert before["skills"] == []
    response = await _assign(lab, space["id"], org["id"], org["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == before["version"] + 1
    assert [(s["name"], s["available"]) for s in body["skills"]] == [
        ("org-skill", True),
        ("space-skill", True),
    ]
    entry = await session.scalar(select(AuditLog).where(AuditLog.action == "agent.skills_changed"))
    assert entry is not None and entry.target_id == lab.bench.agent.id
    assert entry.details == {"skill_ids": sorted([org["id"], space["id"]])}
    cleared = await _assign(lab)
    assert cleared.json()["skills"] == []


async def test_skills_beyond_the_agents_reach_are_refused(lab: Lab, make_space: MakeSpace) -> None:
    space = await made(lab.alice, space_id=lab.space_id)  # the agent is no member
    unknown = str(uuid.uuid4())
    response = await _assign(lab, space["id"], unknown)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "agent.skill_not_assignable"
    assert error["details"] == {"skill_ids": sorted([space["id"], unknown])}
    handbook = await make_space(SpaceKind.OPEN, "Handbuch")
    in_open = await made(lab.admin, space_id=str(handbook.id), name="open-skill")
    assert (await _assign(lab, in_open["id"])).status_code == 200  # the agent reads it


async def test_two_skills_of_one_name_are_refused(lab: Lab) -> None:
    await lab.bench.join(lab.space)
    org = await made(lab.admin)
    space = await made(lab.alice, space_id=lab.space_id)  # the same name, another scope
    response = await _assign(lab, org["id"], space["id"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "agent.skill_names_clash"
    assert response.json()["error"]["details"] == {"names": ["pdf-tools"]}


async def test_assigning_needs_agent_manage_and_the_version(lab: Lab) -> None:
    org = await made(lab.admin)
    for client in (lab.alice, lab.gast):
        refused = await client.get(_url(lab))
        assert (refused.status_code, refused.json()["error"]["code"]) == (404, "agent.not_found")
        put = await client.put(_url(lab), json={"skill_ids": [org["id"]], "version": 1})
        assert (put.status_code, put.json()["error"]["code"]) == (404, "agent.not_found")
    version = (await lab.admin.get(_url(lab))).json()["version"]
    stale = await lab.admin.put(_url(lab), json={"skill_ids": [], "version": version - 1})
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "agent.version_conflict")


async def test_a_run_lists_and_loads_what_it_may_use(lab: Lab) -> None:
    await lab.bench.join(lab.space)
    org = await made(lab.admin, name="org-skill", content="Org text")
    space = await made(lab.alice, space_id=lab.space_id, name="space-skill", content="Lab text")
    await made(lab.admin, name="not-assigned")
    await _assign(lab, org["id"], space["id"])
    listed = await _run_skills(lab)
    assert [(s.name, s.description, s.space_id) for s in listed] == [
        ("org-skill", "Work with PDF files.", None),
        ("space-skill", "Work with PDF files.", lab.space.id),
    ]
    assert not hasattr(listed[0], "content")  # the list never carries the text
    loaded = await _load(lab, "space-skill")
    assert (loaded.name, loaded.content, loaded.space_id) == (
        "space-skill",
        "Lab text",
        lab.space.id,
    )
    assert (await _load(lab, "org-skill")).content == "Org text"
    assert await _load(lab, "not-assigned") is None
    assert await _load(lab, "nothing") is None


async def test_the_person_behind_the_run_must_read_the_space_too(lab: Lab) -> None:
    await lab.bench.join(lab.space)
    org = await made(lab.admin, name="org-skill")
    space = await made(lab.alice, space_id=lab.space_id, name="space-skill")
    await _assign(lab, org["id"], space["id"])
    assert [s.name for s in await _run_skills(lab, "carol")] == ["org-skill"]
    assert await _load(lab, "space-skill", "carol") is None


async def test_leaving_the_space_leaves_the_assignment_unused(lab: Lab) -> None:
    await lab.bench.join(lab.space)
    space = await made(lab.alice, space_id=lab.space_id, name="space-skill")
    await _assign(lab, space["id"])
    await SpaceRepository(lab.bench.session).remove_member(
        lab.space.id, Principal.agent(lab.bench.agent.id)
    )
    shown = (await lab.admin.get(_url(lab))).json()["skills"]
    assert [(s["name"], s["available"]) for s in shown] == [("space-skill", False)]
    assert await _run_skills(lab) == []
    assert await _load(lab, "space-skill") is None


async def test_archived_skills_are_not_used(lab: Lab) -> None:
    org = await made(lab.admin)
    await _assign(lab, org["id"])
    await lab.admin.post(f"{SKILLS}/{org['id']}/archive", json={"version": 1})
    shown = (await lab.admin.get(_url(lab))).json()["skills"]
    assert [(s["state"], s["available"]) for s in shown] == [("archived", False)]
    assert await _run_skills(lab) == []
    assert await _load(lab, "pdf-tools") is None


async def _policy(session: AsyncSession, space: Space, kind: str, *locations: str) -> None:
    space.ai_policy = kind  # type: ignore[assignment]
    space.allowed_locations = list(locations)
    await session.flush()


async def test_the_spaces_ai_policy_decides_for_the_runs_connection(lab: Lab) -> None:
    await lab.bench.join(lab.space)
    space = await made(lab.alice, space_id=lab.space_id, name="space-skill")
    await _assign(lab, space["id"])
    session = lab.bench.session
    await _policy(session, lab.space, "restricted", "eu")
    assert await _run_skills(lab) == []
    assert await _load(lab, "space-skill") is None
    assert [s.name for s in await _run_skills(lab, location=DataLocation("eu"))] == ["space-skill"]
    await _policy(session, lab.space, "none")
    assert await _run_skills(lab, location=DataLocation("eu")) == []


async def test_a_name_two_usable_skills_share_is_left_out(lab: Lab) -> None:
    await lab.bench.join(lab.space)
    org = await made(lab.admin, name="pdf-tools")
    space = await made(lab.alice, space_id=lab.space_id, name="other")
    await _assign(lab, org["id"], space["id"])
    renamed = await lab.alice.patch(
        f"{SKILLS}/{space['id']}", json={"name": "pdf-tools", "version": 1}
    )
    assert renamed.status_code == 200
    assert await _run_skills(lab) == []
    assert await _load(lab, "pdf-tools") is None


async def test_a_put_keeps_assignments_its_caller_does_not_see(lab: Lab) -> None:
    """Replacing touches only skills the caller sees, so it neither reveals nor drops
    the others (an actor that reads no space stands in for such a manager)."""
    await lab.bench.join(lab.space)
    space = await made(lab.alice, space_id=lab.space_id, name="space-skill")
    org = await made(lab.admin, name="org-skill")
    await _assign(lab, space["id"], org["id"])
    session = lab.bench.session
    admin = await actor_of(session, lab.bench.people.users["admin"])
    blind = replace(admin, read_scope=ReadScope.of({}))
    shown = await AgentSkills(session).get(blind, lab.bench.agent.id)
    assert [s.skill.name for s in shown.skills] == ["org-skill"]
    after = await AgentSkills(session).replace(blind, lab.bench.agent.id, [], shown.agent.version)
    assert after.skills == []
    full = (await lab.admin.get(_url(lab))).json()["skills"]
    assert [s["name"] for s in full] == ["space-skill"]
