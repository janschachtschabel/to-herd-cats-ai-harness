"""The AI policy of a space and the no-AI lock (spec 7.3, 11): pure rules for every
policy × data location, the settings and locks through the API (`space.manage`,
`page.moderate`, versions), and the SQL filters "readable by AI"."""

import itertools

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.ai.models import AiConnection, AiPolicy, DataLocation
from app.modules.ai.policy import ANY, NONE, Policy, connection_allowed, strictest
from app.modules.ai.policy_filters import ai_readable, ai_space_ids
from app.modules.audit.models import AuditLog
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.users.models import User
from app.modules.wiki.models import Attachment, Page
from app.modules.wiki.service import PageService
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_wiki import Wiki, new_page

LOCATIONS = list(DataLocation)


def restricted(*locations: DataLocation) -> Policy:
    return Policy(AiPolicy.RESTRICTED, frozenset(locations))


@pytest.mark.parametrize("location", LOCATIONS)
def test_every_policy_against_every_location(location: DataLocation) -> None:
    assert connection_allowed(location, ANY)
    assert not connection_allowed(location, NONE)
    for size in range(len(LOCATIONS) + 1):
        for allowed in itertools.combinations(LOCATIONS, size):
            assert connection_allowed(location, restricted(*allowed)) == (location in allowed)


def test_the_strictest_policy() -> None:
    eu_local = restricted(DataLocation.EU, DataLocation.LOCAL)
    local = restricted(DataLocation.LOCAL)
    assert strictest([]) == ANY
    assert strictest([ANY, ANY]) == ANY
    assert strictest([ANY, eu_local]) == eu_local
    assert strictest([eu_local, local]).locations() == {DataLocation.LOCAL}
    assert strictest([restricted(DataLocation.EU), local]).locations() == frozenset()
    assert strictest([ANY, eu_local, NONE]) == NONE
    assert not connection_allowed(DataLocation.EXTERNAL, strictest([ANY, eu_local]))
    assert Policy.of("restricted", ["eu"]) == restricted(DataLocation.EU)
    assert Policy.of("any", []) == ANY and Policy.of("none") == NONE
    connection = AiConnection(name="EU", data_location=DataLocation.EU)
    assert connection_allowed(connection, eu_local)
    assert not connection_allowed(connection, restricted(DataLocation.LOCAL))


async def test_space_managers_set_the_policy_with_a_version(
    wiki: Wiki, session: AsyncSession
) -> None:
    path = f"/api/spaces/{wiki.space_id}"
    space = (await wiki.admin.get(path)).json()
    assert (space["ai_policy"], space["allowed_locations"]) == ("any", [])
    body = {
        "ai_policy": "restricted",
        "allowed_locations": ["local", "eu"],
        "version": space["version"],
    }
    refused = await wiki.moderator.patch(path, json=body)
    assert refused.status_code == 403
    changed = await wiki.admin.patch(path, json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()["ai_policy"] == "restricted"
    assert changed.json()["allowed_locations"] == ["eu", "local"]
    stale = await wiki.admin.patch(path, json={"ai_policy": "none", "version": space["version"]})
    assert stale.status_code == 409
    readers_see = (await wiki.viewer.get(path)).json()
    assert readers_see["ai_policy"] == "restricted"
    none = await wiki.admin.patch(
        path, json={"ai_policy": "none", "version": changed.json()["version"]}
    )
    assert (none.json()["ai_policy"], none.json()["allowed_locations"]) == ("none", [])
    entries = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "space.updated"))
    ).all()
    assert {"from": [], "to": ["eu", "local"]} in [
        e.details["changes"].get("allowed_locations") for e in entries
    ]


async def test_a_restricted_policy_names_its_locations(wiki: Wiki) -> None:
    path = f"/api/spaces/{wiki.space_id}"
    version = (await wiki.admin.get(path)).json()["version"]
    for body in (
        {"ai_policy": "restricted"},
        {"ai_policy": "restricted", "allowed_locations": []},
        {"ai_policy": "any", "allowed_locations": ["eu"]},
        {"allowed_locations": ["eu"]},
        {"ai_policy": "restricted", "allowed_locations": ["mars"]},
        {"ai_policy": "sometimes"},
    ):
        response = await wiki.admin.patch(path, json={**body, "version": version})
        assert response.status_code == 422, body


async def test_moderators_lock_pages_and_files_for_ai(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Geheim")
    assert page["no_ai"] is False
    lock = f"/api/pages/{page['id']}/ai-lock"
    assert (
        await wiki.editor.put(lock, json={"no_ai": True, "version": page["version"]})
    ).status_code == 403
    locked = await wiki.moderator.put(lock, json={"no_ai": True, "version": page["version"]})
    assert locked.status_code == 200 and locked.json()["no_ai"] is True
    assert locked.json()["version"] == page["version"] + 1
    again = await wiki.moderator.put(lock, json={"no_ai": True, "version": page["version"] + 1})
    assert again.json()["version"] == page["version"] + 1  # unchanged: no new version
    shown = await wiki.editor.get(f"/api/pages/{page['id']}")
    assert shown.json()["no_ai"] is True
    stale = await wiki.moderator.put(lock, json={"no_ai": False, "version": page["version"]})
    assert stale.status_code == 409
    hidden = await wiki.outsider.put(lock, json={"no_ai": False, "version": 2})
    assert hidden.status_code == 404
    upload = await wiki.editor.post(
        f"/api/pages/{page['id']}/attachments", params={"filename": "a.txt"}, content=b"Inhalt"
    )
    attachment = upload.json()
    assert (attachment["no_ai"], attachment["version"]) == (False, 1)
    file_lock = f"/api/attachments/{attachment['id']}/ai-lock"
    assert (await wiki.editor.put(file_lock, json={"no_ai": True, "version": 1})).status_code == 403
    done = await wiki.moderator.put(file_lock, json={"no_ai": True, "version": 1})
    assert done.status_code == 200 and (done.json()["no_ai"], done.json()["version"]) == (True, 2)
    assert (
        await wiki.moderator.put(file_lock, json={"no_ai": False, "version": 1})
    ).status_code == 409
    assert (
        await wiki.outsider.put(file_lock, json={"no_ai": False, "version": 2})
    ).status_code == 404
    listed = (await wiki.editor.get(f"/api/pages/{page['id']}/attachments")).json()["items"]
    assert listed[0]["no_ai"] is True
    audit = {
        (a.action, a.details.get("no_ai")) for a in (await session.scalars(select(AuditLog))).all()
    }
    assert {("page.ai_lock_set", True), ("attachment.ai_lock_set", True)} <= audit


def _file(user: User, page: Page, filename: str, *, no_ai: bool = False) -> Attachment:
    return Attachment(
        org_id=user.org_id,
        space_id=page.space_id,
        page_id=page.id,
        filename=filename,
        mime="text/plain",
        size=1,
        sha256="0" * 64,
        storage_key="x",
        uploaded_by_type="user",
        uploaded_by_id=user.id,
        no_ai=no_ai,
    )


async def _content(
    session: AsyncSession, make_space: MakeSpace, owner_user: User
) -> dict[str, Space]:
    """Per policy a space with an open page and a locked one; on the open page an open
    file and a locked one, on the locked page an open file (hidden with its page)."""
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    pages = PageService(session)
    made = {}
    for name, policy, allowed in (
        ("any", "any", []),
        ("eu", "restricted", ["eu", "local"]),
        ("local", "restricted", ["local"]),
        ("none", "none", []),
    ):
        space = await make_space("team", name)
        space.ai_policy, space.allowed_locations = policy, allowed
        open_page = await pages.create(actor, space.id, None, f"{name} offen")
        locked = await pages.create(actor, space.id, None, f"{name} gesperrt")
        locked.no_ai = True
        session.add_all(
            [
                _file(owner_user, open_page, f"{name} offen.txt"),
                _file(owner_user, open_page, f"{name} datei-gesperrt.txt", no_ai=True),
                _file(owner_user, locked, f"{name} gesperrt.txt"),
            ]
        )
        made[name] = space
    await session.flush()
    return made


EXPECTED = {
    None: {"any", "eu", "local"},
    DataLocation.EXTERNAL: {"any"},
    DataLocation.EU: {"any", "eu"},
    DataLocation.LOCAL: {"any", "eu", "local"},
}


@pytest.mark.parametrize("location", list(EXPECTED))
async def test_readable_by_ai_in_sql(
    session: AsyncSession,
    make_space: MakeSpace,
    owner_user: User,
    location: DataLocation | None,
) -> None:
    """Mutation probes: without the policy clause the `none` space (and, with a
    location, the narrower restricted ones) appears; without the `no_ai` clause the
    locked page and file appear; without the page clause for files, the file on the
    locked page appears; without the organisation clause the other organisation's
    space appears."""
    made = await _content(session, make_space, owner_user)
    stranger_org = Organization(name="Fremd")
    session.add(stranger_org)
    await session.flush()
    stranger = Space(org_id=stranger_org.id, kind="team", name="fremd")
    session.add(stranger)
    await session.flush()
    org_id = owner_user.org_id
    spaces = set((await session.scalars(ai_space_ids(org_id, location))).all())
    names = {name for name, space in made.items() if space.id in spaces}
    assert names == EXPECTED[location]
    assert stranger.id not in spaces
    pages = (
        await session.scalars(select(Page.title).where(ai_readable(Page, org_id, location)))
    ).all()
    assert sorted(pages) == sorted(f"{n} offen" for n in EXPECTED[location])
    files = (
        await session.scalars(
            select(Attachment.filename).where(ai_readable(Attachment, org_id, location))
        )
    ).all()
    assert sorted(files) == sorted(f"{n} offen.txt" for n in EXPECTED[location])


async def test_governance_needs_no_ai_of_ones_own(bench: Bench, make_space: MakeSpace) -> None:
    """Review M5 finding 16: in an organisation with AI, a space admin and a moderator
    who have no AI themselves set the policy and lock a page (`space.manage`,
    `page.moderate`; `ai.use` is not asked)."""
    users = bench.people.users
    space = await make_space(
        SpaceKind.TEAM, members=[(users["alice"], SpaceRole.ADMIN), (users["bob"], "moderator")]
    )
    for who in ("alice", "bob"):
        r = await bench.people.admin.put(
            f"/api/ai/assignments/users/{bench.people.id(who)}",
            json={"no_ai": True, "version": None},
        )
        assert r.status_code == 200, r.text
        me = (await getattr(bench.people, who).get("/api/auth/me")).json()
        assert "ai.use" not in me["permissions"]
    path = f"/api/spaces/{space.id}"
    version = (await bench.people.alice.get(path)).json()["version"]
    changed = await bench.people.alice.patch(path, json={"ai_policy": "none", "version": version})
    assert changed.status_code == 200 and changed.json()["ai_policy"] == "none"
    page = await new_page(bench.people.alice, space.id, "Plan")
    lock = f"/api/pages/{page['id']}/ai-lock"
    locked = await bench.people.bob.put(lock, json={"no_ai": True, "version": page["version"]})
    assert locked.status_code == 200 and locked.json()["no_ai"] is True
