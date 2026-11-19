"""An admin's refused write in a foreign space stays audited (plan M10 task 3b; review
M10 task 1, R1-M2), on the production transaction boundary (`real_db`: the real
`get_session`, which rolls a refused request back): the `space.admin_access` entry of
the look into a foreign team or personal space, and the `calendar.private_read` of a
private event read by admin power, survive a 409 and a 422; nothing was written, so
there is no `calendar.admin_write`."""

import uuid
from typing import Any

from sqlalchemy import select

from app.core.principal import Principal
from app.modules.audit.models import (
    ADMIN_ACCESS,
    CALENDAR_ADMIN_WRITE,
    CALENDAR_PRIVATE_READ,
    AuditLog,
)
from app.modules.spaces.models import Space, SpaceKind, SpaceRole
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User
from tests.factories import login
from tests.factories_calendar import new_calendar, new_event
from tests.real_db import MakeRealClient, RealDb


async def _team_of(real_db: RealDb, email: str) -> uuid.UUID:
    async with real_db.database.session_factory() as session:
        member = await session.scalar(select(User).where(User.email == email))
        assert member is not None
        repo = SpaceRepository(session)
        space = await repo.add(Space(org_id=member.org_id, kind=SpaceKind.TEAM, name="Team"))
        await repo.set_member(space.id, Principal.user(member.id), SpaceRole.MODERATOR)
        await session.commit()
        return space.id


async def _personal_of(real_db: RealDb, email: str) -> uuid.UUID:
    async with real_db.database.session_factory() as session:
        member = await session.scalar(select(User).where(User.email == email))
        assert member is not None
        space = await SpaceRepository(session).get_personal(member.org_id, member.id)
        assert space is not None
        return space.id


async def _entries(real_db: RealDb, email: str) -> list[tuple[str, uuid.UUID]]:
    async with real_db.database.session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == email))
        assert admin is not None
        rows = await session.scalars(select(AuditLog).where(AuditLog.actor_id == admin.id))
        return [(row.action, row.target_id) for row in rows]


def _code(r: Any) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


async def test_an_admins_refused_write_in_a_foreign_space_stays_audited(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    member = await make_real_client()
    await login(member, real_db.member_email)
    team_id = await _team_of(real_db, real_db.member_email)
    personal_id = await _personal_of(real_db, real_db.member_email)
    plain = await new_event(member, (await new_calendar(member, team_id))["id"])
    private = await new_event(
        member, (await new_calendar(member, personal_id))["id"], visibility="private"
    )
    admin = await make_real_client()
    await login(admin, real_db.owner_email)  # the owner: an admin, in neither space
    for event in (plain, private):
        url = f"/api/events/{event['id']}"
        refused = [
            await admin.patch(url, json={"version": 99, "title": "X"}),
            await admin.delete(url, params={"version": 99}),
            await admin.patch(url, json={"version": 1, "ends_at": "2026-11-23T08:00:00+01:00"}),
        ]
        assert [_code(r) for r in refused] == [
            (409, "event.version_conflict"),
            (409, "event.version_conflict"),
            (422, "event.invalid_time"),
        ]
    entries = await _entries(real_db, real_db.owner_email)
    assert sorted(entries) == sorted(
        [
            (ADMIN_ACCESS, team_id),
            (ADMIN_ACCESS, personal_id),
            (CALENDAR_PRIVATE_READ, uuid.UUID(private["id"])),
        ]
    )
    assert CALENDAR_ADMIN_WRITE not in [action for action, _ in entries]
    read = await member.get(f"/api/events/{plain['id']}")
    assert (read.json()["title"], read.json()["version"]) == ("Termin", 1)
