"""Skills over the API (plan M6 task 9, decision 11): organisation-wide skills are
managed with `skill.manage`, a space's skills by its moderators; readers see
organisation-wide skills with `ai.use` and a space's skills with `space.read` there.
Every change of description or content is a version; names are unique per scope;
writes carry `version` (409); every change is audited without the skill's text."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from tests.factories_skills import SKILLS, Lab, create, listed, made


async def _audit(session: AsyncSession, action: str) -> list[AuditLog]:
    rows = await session.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    )
    return list(rows)


async def test_an_admin_makes_an_organisation_wide_skill(lab: Lab, session: AsyncSession) -> None:
    skill = await made(lab.admin, description="  Work with PDF files.  ")
    assert skill["space_id"] is None
    assert (skill["name"], skill["description"], skill["state"], skill["version"]) == (
        "pdf-tools",
        "Work with PDF files.",
        "active",
        1,
    )
    assert skill["content"] == "# PDF\n"
    admin = lab.bench.people.users["admin"]
    assert skill["author"] == {"type": "user", "id": str(admin.id), "name": admin.name}
    assert skill["created_at"] and skill["updated_at"]
    versions = (await lab.admin.get(f"{SKILLS}/{skill['id']}/versions")).json()["items"]
    assert [(v["number"], v["description"]) for v in versions] == [(1, "Work with PDF files.")]
    assert versions[0]["author"]["id"] == str(admin.id) and versions[0]["created_at"]
    [entry] = await _audit(session, "skill.created")
    assert entry.target_id is not None and str(entry.target_id) == skill["id"]
    assert entry.details == {
        "name": "pdf-tools",
        "space_id": None,
        "description_chars": 20,
        "content_chars": 6,
    }


async def test_people_with_ai_read_organisation_wide_skills_but_do_not_manage_them(
    lab: Lab,
) -> None:
    skill = await made(lab.admin)
    assert (await lab.alice.get(f"{SKILLS}/{skill['id']}")).json()["content"] == "# PDF\n"
    assert [s["id"] for s in await listed(lab.alice)] == [skill["id"]]
    refused = await create(lab.alice, name="mine")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "auth.permission_denied"
    patched = await lab.alice.patch(f"{SKILLS}/{skill['id']}", json={"name": "x", "version": 1})
    assert patched.status_code == 403
    archived = await lab.alice.post(f"{SKILLS}/{skill['id']}/archive", json={"version": 1})
    assert archived.status_code == 403


async def test_moderators_manage_their_spaces_skills_and_readers_read_them(lab: Lab) -> None:
    skill = await made(lab.alice, space_id=lab.space_id)
    assert skill["space_id"] == lab.space_id
    bob_sees = await lab.bob.get(f"{SKILLS}/{skill['id']}")
    assert bob_sees.status_code == 200 and bob_sees.json()["content"] == "# PDF\n"
    bob_patch = await lab.bob.patch(f"{SKILLS}/{skill['id']}", json={"name": "x", "version": 1})
    assert bob_patch.status_code == 403
    bob_makes = await create(lab.bob, space_id=lab.space_id, name="bobs")
    assert bob_makes.status_code == 403
    carol_sees = await lab.carol.get(f"{SKILLS}/{skill['id']}")
    assert carol_sees.status_code == 404
    assert carol_sees.json()["error"]["code"] == "skill.not_found"
    assert await listed(lab.carol) == []
    carol_makes = await create(lab.carol, space_id=lab.space_id, name="carols")
    assert carol_makes.status_code == 404
    assert carol_makes.json()["error"]["code"] == "space.not_found"
    admin_patch = await lab.admin.patch(
        f"{SKILLS}/{skill['id']}", json={"name": "by-admin", "version": 1}
    )
    assert admin_patch.status_code == 200, admin_patch.text


async def test_names_are_checked_and_unique_per_scope(lab: Lab) -> None:
    bad = await create(lab.admin, name="Bad Name")
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "skill.name_invalid")
    empty = await create(lab.admin, description=" ")
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "skill.description_invalid")
    blank = await create(lab.admin, content="\n")
    assert (blank.status_code, blank.json()["error"]["code"]) == (422, "skill.content_invalid")
    huge = await create(lab.admin, content="x" * 50_001)
    assert (huge.status_code, huge.json()["error"]["code"]) == (422, "skill.content_invalid")
    first = await made(lab.admin)
    again = await create(lab.admin)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "skill.name_taken")
    in_space = await made(lab.alice, space_id=lab.space_id)  # another scope: allowed
    assert in_space["name"] == first["name"]
    clash = await lab.admin.patch(
        f"{SKILLS}/{first['id']}", json={"name": "pdf-tools", "version": 1}
    )
    assert clash.status_code == 200  # its own name
    await made(lab.admin, name="other")
    taken = await lab.admin.patch(f"{SKILLS}/{first['id']}", json={"name": "other", "version": 2})
    assert (taken.status_code, taken.json()["error"]["code"]) == (409, "skill.name_taken")


async def test_changes_make_versions_and_stale_writes_conflict(
    lab: Lab, session: AsyncSession
) -> None:
    skill = await made(lab.admin)
    url = f"{SKILLS}/{skill['id']}"
    renamed = (await lab.admin.patch(url, json={"name": "pdf", "version": 1})).json()
    assert (renamed["name"], renamed["version"]) == ("pdf", 2)
    changed = await lab.admin.patch(url, json={"content": "# Neu\n", "version": 2})
    assert changed.json()["version"] == 3
    same = await lab.admin.patch(url, json={"description": "Work with PDF files.", "version": 3})
    assert same.status_code == 200
    stale = await lab.admin.patch(url, json={"content": "x", "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "skill.version_conflict"
    assert stale.json()["error"]["details"] == {"current_version": 4}
    null = await lab.admin.patch(url, json={"content": None, "version": 4})
    assert null.status_code == 422
    versions = (await lab.admin.get(f"{url}/versions")).json()["items"]
    assert [v["number"] for v in versions] == [2, 1]  # the rename and the same text: none
    first = (await lab.admin.get(f"{url}/versions/1")).json()
    assert (first["number"], first["content"]) == (1, "# PDF\n")
    assert (await lab.admin.get(f"{url}/versions/3")).status_code == 404
    entries = await _audit(session, "skill.updated")
    assert [e.details for e in entries] == [
        {"changes": {"name": {"from": "pdf-tools", "to": "pdf"}}},
        {"changes": {}, "content_chars": 6, "version_number": 2},
        {"changes": {}},
    ]


async def test_an_old_version_is_restored_as_a_new_one(lab: Lab, session: AsyncSession) -> None:
    skill = await made(lab.alice, space_id=lab.space_id)
    url = f"{SKILLS}/{skill['id']}"
    await lab.alice.patch(url, json={"content": "# Zwei\n", "description": "B", "version": 1})
    stale = await lab.alice.post(f"{url}/versions/1/restore", json={"version": 1})
    assert stale.status_code == 409
    refused = await lab.bob.post(f"{url}/versions/1/restore", json={"version": 2})
    assert refused.status_code == 403
    missing = await lab.alice.post(f"{url}/versions/9/restore", json={"version": 2})
    assert (missing.status_code, missing.json()["error"]["code"]) == (
        404,
        "skill.version_not_found",
    )
    restored = await lab.alice.post(f"{url}/versions/1/restore", json={"version": 2})
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert (body["content"], body["description"], body["version"]) == (
        "# PDF\n",
        "Work with PDF files.",
        3,
    )
    versions = (await lab.bob.get(f"{url}/versions")).json()["items"]
    assert [v["number"] for v in versions] == [3, 2, 1]
    [entry] = await _audit(session, "skill.restored")
    assert entry.details == {"from_number": 1, "version_number": 3}


async def test_skills_are_archived_not_deleted(lab: Lab, session: AsyncSession) -> None:
    skill = await made(lab.admin)
    url = f"{SKILLS}/{skill['id']}"
    archived = await lab.admin.post(f"{url}/archive", json={"version": 1})
    assert (archived.json()["state"], archived.json()["version"]) == ("archived", 2)
    twice = await lab.admin.post(f"{url}/archive", json={"version": 2})
    assert (twice.status_code, twice.json()["error"]["code"]) == (409, "skill.state_conflict")
    assert [s["id"] for s in await listed(lab.alice, state="archived")] == [skill["id"]]
    assert await listed(lab.alice, state="active") == []
    again = await create(lab.admin)  # the archived skill keeps its name
    assert again.status_code == 409
    back = await lab.admin.post(f"{url}/unarchive", json={"version": 2})
    assert back.json()["state"] == "active"
    not_archived = await lab.admin.post(f"{url}/unarchive", json={"version": 3})
    assert not_archived.status_code == 409
    assert [e.action for e in await _audit(session, "skill.archived")] == ["skill.archived"]
    assert len(await _audit(session, "skill.unarchived")) == 1


async def test_the_list_filters_and_pages(lab: Lab) -> None:
    org = await made(lab.admin, name="beta")
    space = await made(lab.alice, space_id=lab.space_id, name="alpha")
    await made(lab.admin, name="gamma-pdf")
    assert [s["name"] for s in await listed(lab.alice)] == ["alpha", "beta", "gamma-pdf"]
    assert [s["id"] for s in await listed(lab.alice, space_id=lab.space_id)] == [space["id"]]
    assert [s["name"] for s in await listed(lab.alice, org_wide=True)] == ["beta", "gamma-pdf"]
    assert [s["id"] for s in await listed(lab.alice, org_wide=False)] == [space["id"]]
    assert [s["id"] for s in await listed(lab.alice, q="ET")] == [org["id"]]
    assert await listed(lab.alice, q="%") == []
    assert "content" not in (await listed(lab.alice))[0]
    first = (await lab.alice.get(SKILLS, params={"limit": 2})).json()
    assert [s["name"] for s in first["items"]] == ["alpha", "beta"]
    rest = await lab.alice.get(SKILLS, params={"limit": 2, "cursor": first["next_cursor"]})
    assert [s["name"] for s in rest.json()["items"]] == ["gamma-pdf"]
    assert rest.json()["next_cursor"] is None
    hidden = await lab.carol.get(SKILLS, params={"space_id": lab.space_id})
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "space.not_found")
