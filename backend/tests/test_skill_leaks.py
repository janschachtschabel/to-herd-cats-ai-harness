"""What skills must not give away (plan M6 review focus 1): a skill of a space one
cannot read answers every route exactly like an unknown id and shows up in no list,
filter or name search; a space member without AI sees no skill; the audit log never
holds a skill's text."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.modules.audit.models import AuditLog
from app.modules.spaces.repository import SpaceRepository
from tests.factories_skills import SKILLS, Lab, listed, made
from tests.factories_spaces import principal_of
from tests.route_table import BODIES, ROUTES, concrete
from tests.test_skill_transfer import skill_md, zipped

SECRET_TEXT = "GEHEIMER-INHALT"
SECRET_DESCRIPTION = "GEHEIME-BESCHREIBUNG"


async def test_a_skill_of_an_unreadable_space_is_like_an_unknown_id(lab: Lab) -> None:
    skill = await made(lab.alice, space_id=lab.space_id, name="geheim")
    for skill_id in (skill["id"], None):  # the real one, and an id nobody has
        answers = []
        for method, template, guard in ROUTES:
            if guard != "skill" or "{skill_id}" not in template:
                continue
            path = concrete(template, skill_id=skill_id)
            response = await lab.carol.request(method, path, json=BODIES.get((method, template)))
            answers.append((method, template, response.status_code, response.json()))
        for method, template, status, body in answers:
            assert status == 404, (method, template, body)
            assert body["error"]["code"] == "skill.not_found", (method, template)
            assert set(body["error"]) == {"code", "message", "trace_id"}


async def test_lists_and_searches_leave_unreadable_skills_out(lab: Lab) -> None:
    await made(lab.alice, space_id=lab.space_id, name="geheim")
    await made(lab.admin, name="offen")
    assert [s["name"] for s in await listed(lab.carol)] == ["offen"]
    for params in ({"q": "geh"}, {"org_wide": False}, {"state": "active", "q": "e"}):
        assert "geheim" not in [s["name"] for s in await listed(lab.carol, **params)], params
    assert [s["name"] for s in await listed(lab.bob, q="geh")] == ["geheim"]


async def test_a_member_without_ai_sees_no_skill_of_their_space(lab: Lab) -> None:
    """The guest is a member of the space but has no `ai.use` (guests never do)."""
    gast = lab.bench.people.users["gast"]
    await SpaceRepository(lab.bench.session).set_member(
        lab.space.id, principal_of(gast), SpaceRole.MODERATOR
    )
    skill = await made(lab.alice, space_id=lab.space_id)
    for path in (SKILLS, f"{SKILLS}/{skill['id']}", f"{SKILLS}/{skill['id']}/export"):
        response = await lab.gast.get(path)
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "skill.not_found",
        ), path
    made_by_gast = await lab.gast.post(
        SKILLS, json={"space_id": lab.space_id, "name": "g", "description": "d", "content": "c"}
    )
    assert made_by_gast.status_code == 404


async def test_the_audit_log_never_holds_a_skills_text(lab: Lab, session: AsyncSession) -> None:
    skill = await made(
        lab.alice, space_id=lab.space_id, description=SECRET_DESCRIPTION, content=SECRET_TEXT
    )
    url = f"{SKILLS}/{skill['id']}"
    await lab.alice.patch(
        url,
        json={"description": SECRET_DESCRIPTION + "2", "content": SECRET_TEXT + "2", "version": 1},
    )
    await lab.alice.post(f"{url}/versions/1/restore", json={"version": 2})
    await lab.alice.post(f"{url}/archive", json={"version": 3})
    archive = zipped({"z/SKILL.md": skill_md("z", SECRET_DESCRIPTION, SECRET_TEXT)})
    await lab.alice.post(f"{SKILLS}/import", content=archive, params={"space_id": lab.space_id})
    rows = list(await session.scalars(select(AuditLog).where(AuditLog.action.like("skill.%"))))
    assert {r.action for r in rows} == {
        "skill.created",
        "skill.updated",
        "skill.restored",
        "skill.archived",
        "skill.imported",
    }
    dumped = json.dumps([r.details for r in rows])
    assert "GEHEIM" not in dumped
