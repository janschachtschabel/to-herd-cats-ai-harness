"""The append-only audit log: what is written, in which transaction, and who reads it."""

from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository
from app.modules.groups.models import Group
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space
from app.modules.users.models import User
from tests.factories import PASSWORD
from tests.factories_spaces import personal_space_of

AUDIT = "/api/admin/audit"


async def audit_rows(session: AsyncSession, **where: Any) -> list[AuditLog]:
    stmt = select(AuditLog).filter_by(**where).order_by(AuditLog.created_at, AuditLog.id)
    return list((await session.scalars(stmt)).all())


async def test_space_member_change_is_audited(
    owner: AsyncClient, owner_user: User, team_space: Space, member: User, session: AsyncSession
) -> None:
    base = f"/api/spaces/{team_space.id}/members"
    entry = {"member_type": "user", "member_id": str(member.id), "role": "editor"}
    assert (await owner.put(base, json=entry)).status_code == 200
    assert (await owner.delete(f"{base}/user/{member.id}")).status_code == 204
    rows = await audit_rows(session, target_id=team_space.id)
    assert [r.action for r in rows] == [
        "space.admin_access",  # the owner is no member of the space
        "space.member_set",
        "space.member_removed",
    ]
    first = rows[1]
    assert (first.org_id, first.actor_type, first.actor_id) == (
        owner_user.org_id,
        "user",
        owner_user.id,
    )
    assert first.target_type == "space"
    assert first.details == {"member_type": "user", "member_id": str(member.id), "role": "editor"}
    assert first.ip == "127.0.0.1"  # the client address of the request
    assert first.created_at is not None


async def test_admin_access_to_foreign_personal_space_is_audited_once_per_day(
    owner: AsyncClient, member: User, session: AsyncSession
) -> None:
    personal = await personal_space_of(session, member)
    for _ in range(3):
        assert (await owner.get(f"/api/spaces/{personal.id}")).status_code == 200
    assert (await owner.get(f"/api/spaces/{personal.id}/members")).status_code == 200
    rows = await audit_rows(session, action="space.admin_access")
    assert len(rows) == 1
    assert (rows[0].target_type, rows[0].target_id) == ("space", personal.id)
    assert rows[0].details == {"kind": "personal"}

    # Another UTC day is another entry.
    rows[0].created_at = utcnow() - timedelta(days=1)
    await session.flush()
    assert (await owner.get(f"/api/spaces/{personal.id}")).status_code == 200
    assert len(await audit_rows(session, action="space.admin_access")) == 2


async def test_admin_access_is_audited_only_without_membership(
    owner: AsyncClient,
    owner_user: User,
    make_space,
    make_group,
    open_space: Space,
    session: AsyncSession,
) -> None:
    team = await make_group(members=[owner_user])
    own = await make_space("team", members=[(owner_user, "viewer")])
    via_group = await make_space("team", members=[(team, "viewer")])
    foreign = await make_space("team")
    for space in (
        open_space,
        own,
        via_group,
        foreign,
        await personal_space_of(session, owner_user),
    ):
        assert (await owner.get(f"/api/spaces/{space.id}")).status_code == 200
    rows = await audit_rows(session, action="space.admin_access")
    assert [r.target_id for r in rows] == [foreign.id]
    assert rows[0].details == {"kind": "team"}


async def test_admin_access_is_not_audited_for_lists(
    owner: AsyncClient, member: User, session: AsyncSession
) -> None:
    assert (await owner.get("/api/spaces")).status_code == 200
    assert await audit_rows(session, action="space.admin_access") == []


async def test_audit_is_not_written_when_change_fails(
    owner: AsyncClient, team_space: Space, member: User, session: AsyncSession, monkeypatch
) -> None:
    """The entry is part of the change's transaction: if the request fails after the
    service wrote both, neither stays."""
    from app.modules.spaces import router as spaces_router

    def _explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced failure after the change")

    monkeypatch.setattr(spaces_router.SpaceMemberOut, "model_validate", _explode)
    entry = {"member_type": "user", "member_id": str(member.id), "role": "editor"}
    r = await owner.put(f"/api/spaces/{team_space.id}/members", json=entry)
    assert r.status_code == 500
    assert await audit_rows(session, target_id=team_space.id) == []
    members = await owner.get(f"/api/spaces/{team_space.id}/members")
    assert members.json()["items"] == []


async def test_user_changes_are_audited_without_secrets(
    owner: AsyncClient, member: User, session: AsyncSession
) -> None:
    created = await owner.post(
        "/api/admin/users",
        json={"email": "mia@example.com", "name": "Mia", "password": "mia-password-123"},
    )
    mia = created.json()
    base = f"/api/admin/users/{member.id}"
    r = await owner.patch(base, json={"name": "Maxi", "system_role": "admin", "version": 1})
    assert r.status_code == 200
    r = await owner.patch(base, json={"password": "brand-new-password", "version": 2})
    assert r.status_code == 200
    assert (await owner.post(f"{base}/deactivate")).status_code == 204
    assert (await owner.post(f"{base}/deactivate")).status_code == 204  # no change
    assert (await owner.post(f"{base}/reactivate")).status_code == 204
    assert (await owner.post(f"{base}/reactivate")).status_code == 204  # no change

    rows = await audit_rows(session, target_type="user")
    assert [(r.action, str(r.target_id)) for r in rows] == [
        ("user.created", mia["id"]),
        ("user.updated", str(member.id)),
        ("user.password_changed", str(member.id)),
        ("user.deactivated", str(member.id)),
        ("user.reactivated", str(member.id)),
    ]
    assert rows[0].details == {"system_role": "member"}
    assert rows[1].details == {
        "changes": {
            "name": {"from": "Max Member", "to": "Maxi"},
            "system_role": {"from": "member", "to": "admin"},
        }
    }
    stored = (await session.scalars(select(User.password_hash))).all()
    for row in rows:
        text = repr(row.details)
        for secret in ("mia-password-123", "brand-new-password", PASSWORD, *stored):
            assert secret is None or secret not in text


async def test_group_changes_are_audited(
    owner: AsyncClient, member: User, session: AsyncSession
) -> None:
    group = (await owner.post("/api/admin/groups", json={"name": "Team"})).json()
    base = f"/api/admin/groups/{group['id']}"
    await owner.patch(base, json={"name": "Team A", "version": 1})
    ref = {"member_type": "user", "member_id": str(member.id)}
    await owner.post(f"{base}/members", json=ref)
    await owner.post(f"{base}/members", json=ref)  # already a member: nothing happens
    await owner.delete(f"{base}/members/user/{member.id}")
    await owner.delete(base)
    rows = await audit_rows(session, target_type="group")
    assert [r.action for r in rows] == [
        "group.created",
        "group.updated",
        "group.member_added",
        "group.member_removed",
        "group.deleted",
    ]
    assert rows[0].details == {"name": "Team"}
    assert rows[1].details == {"changes": {"name": {"from": "Team", "to": "Team A"}}}
    assert rows[2].details == ref
    assert rows[4].details == {"name": "Team A"}


async def test_space_changes_are_audited(member_client: AsyncClient, session) -> None:
    space = (await member_client.post("/api/spaces", json={"kind": "team", "name": "Apfel"})).json()
    r = await member_client.patch(
        f"/api/spaces/{space['id']}", json={"description": "Obst", "version": 1}
    )
    assert r.status_code == 200
    rows = await audit_rows(session, target_type="space")
    assert [(r.action, str(r.target_id)) for r in rows] == [
        ("space.created", space["id"]),
        ("space.updated", space["id"]),
    ]
    assert rows[0].details == {"kind": "team", "name": "Apfel"}
    assert rows[1].details == {"changes": {"description": {"from": None, "to": "Obst"}}}


async def test_member_cannot_read_audit(
    member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    for client in (member_client, guest_client):
        r = await client.get(AUDIT)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "auth.permission_denied"


async def test_audit_list_is_newest_first_filtered_and_paginated(
    owner: AsyncClient, owner_user: User, make_user
) -> None:
    for name in ("A", "B", "C"):
        await owner.post("/api/admin/groups", json={"name": name})
    await owner.post("/api/spaces", json={"kind": "open", "name": "Handbuch"})

    page = (await owner.get(AUDIT, params={"limit": 2})).json()
    assert [e["action"] for e in page["items"]] == ["space.created", "group.created"]
    assert page["items"][1]["details"] == {"name": "C"}
    rest = (await owner.get(AUDIT, params={"limit": 2, "cursor": page["next_cursor"]})).json()
    assert [e["details"]["name"] for e in rest["items"]] == ["B", "A"]
    assert rest["next_cursor"] is None
    entry = rest["items"][0]
    assert set(entry) == {
        "id",
        "actor_type",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "details",
        "ip",
        "created_at",
    }
    assert entry["actor_id"] == str(owner_user.id) and entry["ip"] == "127.0.0.1"

    groups = (await owner.get(AUDIT, params={"action": "group.created"})).json()["items"]
    assert len(groups) == 3
    other = await make_user("admin")
    mine = (await owner.get(AUDIT, params={"actor_id": str(owner_user.id)})).json()["items"]
    assert len(mine) == 4
    theirs = (await owner.get(AUDIT, params={"actor_id": str(other.id)})).json()["items"]
    assert theirs == []
    assert (await owner.get(AUDIT, params={"limit": 101})).status_code == 422
    assert (await owner.get(AUDIT, params={"cursor": "nope"})).status_code == 422


async def test_other_organisations_entries_are_invisible(
    owner: AsyncClient, session: AsyncSession, make_user
) -> None:
    elsewhere = Organization(name="Elsewhere", slug="elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user("owner", organization=elsewhere)
    session.add(
        AuditLog(
            org_id=elsewhere.id,
            actor_type="user",
            actor_id=stranger.id,
            action="group.created",
            target_type="group",
            target_id=stranger.id,
        )
    )
    await session.flush()
    assert (await owner.get(AUDIT)).json()["items"] == []


def test_the_repository_only_appends() -> None:
    for verb in ("update", "delete", "remove", "merge"):
        assert not any(name.startswith(verb) for name in dir(AuditRepository)), verb


async def test_refused_changes_leave_no_entry(
    member_client: AsyncClient, session: AsyncSession, group: Group
) -> None:
    assert (await member_client.post("/api/admin/groups", json={"name": "X"})).status_code == 403
    assert (await member_client.delete(f"/api/admin/groups/{group.id}")).status_code == 403
    assert await audit_rows(session) == []
