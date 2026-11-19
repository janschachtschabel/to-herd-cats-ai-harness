"""Calendar rights (plan M10 decision 2): `calendar.read` from viewer, `calendar.write`
from editor, `calendar.moderate` from moderator, all through the one check; guests
only where they are members. `calendar.manage` is an admin right; `calendar.sync` is
derived: every active person but guests while the organisation's switch is on (off by
default, audited when turned). A run's read and write scope hold calendars like
everything else."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, member_space_ids
from app.core.actor import ReadScope, WriteScope
from app.core.errors import Forbidden, NotFound
from app.core.pagination import PageParams
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import AuditLog
from app.modules.calendars.repository import CalendarRepository
from app.modules.calendars.service import CalendarService, NewCalendar
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_calendar import actor_of
from tests.factories_spaces import MakeSpace, personal_space_of

RIGHTS = (Action.CALENDAR_READ, Action.CALENDAR_WRITE, Action.CALENDAR_MODERATE)


async def test_roles_grant_calendar_rights(
    session: AsyncSession, make_user: MakeUser, make_space: MakeSpace
) -> None:
    viewer, editor, moderator, member = [await make_user() for _ in range(4)]
    guest, lone_guest = await make_user(SystemRole.GUEST), await make_user(SystemRole.GUEST)
    team = await make_space(
        "team",
        members=[(viewer, "viewer"), (editor, "editor"), (moderator, "moderator")]
        + [(guest, "viewer")],
    )
    open_ = await make_space("open")
    expected = {  # (read, write, moderate) in the team space, then in the open space
        viewer.id: ((True, False, False), (True, False, False)),
        editor.id: ((True, True, False), (True, False, False)),
        moderator.id: ((True, True, True), (True, False, False)),
        member.id: ((False, False, False), (True, False, False)),
        guest.id: ((True, False, False), (False, False, False)),
        lone_guest.id: ((False, False, False), (False, False, False)),
    }
    for user in (viewer, editor, moderator, member, guest, lone_guest):
        actor = await actor_of(session, user)
        for space, rights in zip((team, open_), expected[user.id], strict=True):
            held = tuple([await can(session, actor, a, space.id) for a in RIGHTS])
            assert held == rights, (user.name, space.kind)
    admin = await actor_of(session, await make_user(SystemRole.ADMIN))
    for action in (*RIGHTS, Action.CALENDAR_MANAGE):
        assert await can(session, admin, action, team.id if action in RIGHTS else None)
    member_actor = await actor_of(session, member)
    assert not await can(session, member_actor, Action.CALENDAR_MANAGE)


async def test_calendar_sync_follows_the_organisation_switch(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    guest_client: AsyncClient,
    owner_user: User,
    make_user: MakeUser,
) -> None:
    async def permissions(client: AsyncClient) -> set[str]:
        return set((await client.get("/api/auth/me")).json()["permissions"])

    url = "/api/admin/calendar-settings"
    assert "calendar.manage" in await permissions(owner)
    for client in (owner, member_client, guest_client):
        assert "calendar.sync" not in await permissions(client)  # off by default
    r = await member_client.put(url, json={"sync_enabled": True, "version": 1})
    assert (r.status_code, r.json()["error"]["code"]) == (403, "auth.permission_denied")
    assert (await member_client.get(url)).status_code == 403
    assert (await owner.get(url)).json() == {"sync_enabled": False, "version": 1}

    r = await owner.put(url, json={"sync_enabled": True, "version": 1})
    assert r.status_code == 200, r.text
    assert r.json() == {"sync_enabled": True, "version": 2}
    assert "calendar.sync" in await permissions(owner)
    assert "calendar.sync" in await permissions(member_client)
    assert "calendar.sync" not in await permissions(guest_client)  # guests never
    stale = await owner.put(url, json={"sync_enabled": False, "version": 1})
    assert (stale.status_code, stale.json()["error"]["code"]) == (
        409,
        "calendar.settings_version_conflict",
    )
    gone = await make_user(is_active=False)
    actor = Actor(gone.org_id, Principal.user(gone.id), SystemRole.MEMBER, frozenset())
    assert not await can(session, actor, Action.CALENDAR_SYNC)  # deactivated: no
    entries = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "calendar.settings_set"))
    ).all()
    assert [(e.target_id, e.details) for e in entries] == [
        (owner_user.org_id, {"sync_enabled": {"from": False, "to": True}})
    ]

    r = await owner.put(url, json={"sync_enabled": False, "version": 2})
    assert r.status_code == 200, r.text
    assert "calendar.sync" not in await permissions(member_client)
    again = await owner.put(url, json={"sync_enabled": False, "version": 3})  # no change
    assert again.status_code == 200
    count = len(
        (
            await session.scalars(
                select(AuditLog).where(AuditLog.action == "calendar.settings_set")
            )
        ).all()
    )
    assert count == 2  # a setting that changed nothing is not audited


async def test_run_scopes_apply_to_calendar_rights(
    session: AsyncSession, make_user: MakeUser, make_space: MakeSpace
) -> None:
    person = await make_user()
    here = await make_space("team", "Hier", members=[(person, "moderator")])
    there = await make_space("team", "Dort", members=[(person, "moderator")])
    service = CalendarService(session)
    plain = await actor_of(session, person)
    elsewhere = await service.create(plain, there.id, NewCalendar("Dort"))
    await service.create(plain, here.id, NewCalendar("Hier"))

    scoped = Actor(
        plain.org_id,
        plain.principal,
        plain.system_role,
        plain.group_ids,
        read_scope=ReadScope.of({here.id: SpaceRole.MODERATOR}),
    )
    ids = set((await session.scalars(member_space_ids(scoped))).all())
    assert there.id not in ids and here.id in ids
    page = await service.list(scoped, PageParams(limit=100))
    assert {c.space_id for c in page.items} == {here.id}
    assert not await can(session, scoped, Action.CALENDAR_READ, there.id)
    with pytest.raises(NotFound) as hidden:
        await service.readable(scoped, elsewhere.id)
    assert hidden.value.code == "calendar.not_found"

    writing = Actor(
        plain.org_id,
        plain.principal,
        plain.system_role,
        plain.group_ids,
        write_scope=WriteScope.of([here.id]),
    )
    assert await can(session, writing, Action.CALENDAR_READ, there.id)
    for action in (Action.CALENDAR_WRITE, Action.CALENDAR_MODERATE):
        assert not await can(session, writing, action, there.id), action
        assert await can(session, writing, action, here.id), action
    with pytest.raises(Forbidden):
        await service.create(writing, there.id, NewCalendar("Nein"))
    with pytest.raises(Forbidden):
        await service.archive(writing, elsewhere.id, elsewhere.version)
    assert (await service.readable(writing, elsewhere.id)).id == elsewhere.id


async def test_the_named_list_holds_to_a_read_scope(
    session: AsyncSession, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R1-M7: `list_in` under a run's read scope lists only a space of the scope, and
    makes no default calendar (a run writes nothing it was not asked to)."""
    person = await make_user()
    here = await make_space("team", "Hier", members=[(person, "moderator")])
    there = await make_space("team", "Dort", members=[(person, "moderator")])
    own = await personal_space_of(session, person)
    service = CalendarService(session)
    plain = await actor_of(session, person)
    made = await service.create(plain, here.id, NewCalendar("Hier"))
    await service.create(plain, there.id, NewCalendar("Dort"))
    roles = {here.id: SpaceRole.MODERATOR, own.id: SpaceRole.MODERATOR}
    scoped = Actor(
        plain.org_id,
        plain.principal,
        plain.system_role,
        plain.group_ids,
        read_scope=ReadScope.of(roles),
    )
    page = await service.list_in(scoped, here.id, PageParams(limit=100))
    assert [c.id for c in page.items] == [made.id]
    with pytest.raises(NotFound) as hidden:
        await service.list_in(scoped, there.id, PageParams(limit=100))
    assert hidden.value.code == "space.not_found"
    assert (await service.list_in(scoped, own.id, PageParams(limit=100))).items == []
    assert await CalendarRepository(session, plain.org_id).default_of(own.id) is None
