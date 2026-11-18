"""Every administration route refuses people without the right, and no route is missed:
the table below must list exactly the app's `/api/admin` routes."""

from fastapi.routing import APIRoute, iter_route_contexts
from httpx import AsyncClient
from uuid_utils.compat import uuid7

from app.modules.groups.models import Group
from app.modules.users.models import User
from app.web.public import create_public_app


def _admin_routes() -> set[tuple[str, str]]:
    found = set()
    for context in iter_route_contexts(create_public_app().routes):
        route = context.original_route
        if isinstance(route, APIRoute) and context.path.startswith("/api/admin"):
            found |= {(method, context.path) for method in route.methods}
    return found


def _table(user: User, group: Group) -> list[tuple[str, str, str, dict[str, object] | None]]:
    """(method, template, concrete path, valid body)."""
    new_user = {"email": "neu@example.com", "name": "Neu", "password": "a-long-password"}
    users, groups, inspect = "/api/admin/users", "/api/admin/groups", "/api/admin/dm-inspect"
    grant = {"conversation_id": str(uuid7()), "reason": "a reason of some length"}
    member_ref = {"member_type": "user", "member_id": str(user.id)}
    providers = "/api/admin/oidc-providers"
    calendar = "/api/admin/calendar-settings"
    new_provider = {"kind": "google", "client_id": "c", "client_secret": {"value": "s"}}
    return [
        ("GET", "/api/admin/audit", "/api/admin/audit", None),
        ("GET", users, users, None),
        ("POST", users, users, new_user),
        ("PATCH", f"{users}/{{user_id}}", f"{users}/{user.id}", {"name": "X", "version": 1}),
        ("POST", f"{users}/{{user_id}}/deactivate", f"{users}/{user.id}/deactivate", None),
        ("POST", f"{users}/{{user_id}}/reactivate", f"{users}/{user.id}/reactivate", None),
        ("POST", f"{users}/{{user_id}}/sign-out", f"{users}/{user.id}/sign-out", None),
        ("POST", f"{users}/{{user_id}}/totp/reset", f"{users}/{user.id}/totp/reset", None),
        ("GET", f"{users}/pending/count", f"{users}/pending/count", None),
        ("POST", f"{users}/{{user_id}}/approve", f"{users}/{user.id}/approve", {"version": 1}),
        ("POST", f"{users}/{{user_id}}/reject", f"{users}/{user.id}/reject", {"version": 1}),
        ("GET", f"{users}/{{user_id}}/identities", f"{users}/{user.id}/identities", None),
        (
            "DELETE",
            f"{users}/{{user_id}}/identities/{{identity_id}}",
            f"{users}/{user.id}/identities/{uuid7()}",
            None,
        ),
        ("GET", providers, providers, None),
        ("POST", providers, providers, new_provider),
        ("GET", f"{providers}/{{provider_id}}", f"{providers}/{uuid7()}", None),
        (
            "PATCH",
            f"{providers}/{{provider_id}}",
            f"{providers}/{uuid7()}",
            {"name": "X", "version": 1},
        ),
        (
            "DELETE",
            f"{providers}/{{provider_id}}",
            f"{providers}/{uuid7()}?version=1",
            None,
        ),
        ("POST", f"{providers}/{{provider_id}}/check", f"{providers}/{uuid7()}/check", None),
        ("GET", groups, groups, None),
        ("POST", groups, groups, {"name": "Neu"}),
        ("GET", f"{groups}/{{group_id}}", f"{groups}/{group.id}", None),
        ("PATCH", f"{groups}/{{group_id}}", f"{groups}/{group.id}", {"name": "Y", "version": 1}),
        ("DELETE", f"{groups}/{{group_id}}", f"{groups}/{group.id}", None),
        ("GET", f"{groups}/{{group_id}}/members", f"{groups}/{group.id}/members", None),
        ("POST", f"{groups}/{{group_id}}/members", f"{groups}/{group.id}/members", member_ref),
        (
            "DELETE",
            f"{groups}/{{group_id}}/members/{{member_type}}/{{member_id}}",
            f"{groups}/{group.id}/members/user/{user.id}",
            None,
        ),
        ("GET", calendar, calendar, None),
        ("PUT", calendar, calendar, {"sync_enabled": True, "version": 1}),
        ("GET", inspect, f"{inspect}?user_id={user.id}", None),
        ("POST", inspect, inspect, grant),
        (
            "GET",
            f"{inspect}/{{inspection_id}}/messages",
            f"{inspect}/{uuid7()}/messages",
            None,
        ),
    ]


async def test_every_admin_route_is_listed(member: User, group: Group) -> None:
    listed = {(method, template) for method, template, _, _ in _table(member, group)}
    assert listed == _admin_routes()


async def test_every_admin_route_needs_its_right(
    member_client: AsyncClient, guest_client: AsyncClient, member: User, group: Group
) -> None:
    for client in (member_client, guest_client):
        for method, _, path, body in _table(member, group):
            response = await client.request(method, path, json=body)
            assert response.status_code == 403, (method, path, response.text)
            assert response.json()["error"]["code"] == "auth.permission_denied"


async def test_unknown_ids_do_not_reveal_anything_to_the_unprivileged(
    member_client: AsyncClient,
) -> None:
    """The right is checked before the id is looked up: 403, never 404."""
    for path in (f"/api/admin/users/{uuid7()}/deactivate", f"/api/admin/groups/{uuid7()}"):
        method = "POST" if path.endswith("deactivate") else "GET"
        assert (await member_client.request(method, path)).status_code == 403


async def test_patch_bodies_cannot_set_protected_fields(
    owner: AsyncClient, member: User, group: Group, team_space
) -> None:
    """Fields a PATCH does not offer are refused (422), never silently applied."""
    targets = (
        (f"/api/admin/users/{member.id}", member.version, ("is_active", "email", "org_id", "id")),
        (f"/api/admin/groups/{group.id}", group.version, ("org_id", "id")),
        (f"/api/spaces/{team_space.id}", team_space.version, ("kind", "org_id", "owner_user_id")),
    )
    for path, version, fields in targets:
        for field in fields:
            r = await owner.patch(path, json={field: str(uuid7()), "version": version})
            assert r.status_code == 422, (path, field)
    r = await owner.patch(
        f"/api/admin/users/{member.id}",
        json={"password_hash": "x", "version": member.version},
    )
    assert r.status_code == 422
