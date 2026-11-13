"""Every `/api` route is in this table with the guard it needs, and the guard holds.

A new route that is not listed fails `test_every_api_route_is_listed`, so it cannot
ship without a decision on who may call it. Guards:
- `public`: no session needed (login; logout, which only ends the session it is sent
  with and answers 204 without one).
- `session`: any logged-in person; anonymous → 401.
- `admin`: an administration right; members and guests → 403
  (`test_route_guards.py` checks every one of these).
- `space`: a role in the space; anonymous → 401, a member without a role in a team
  space → 404 (the space's existence is not revealed).
Every unsafe method also needs the CSRF header (→ 403 `auth.csrf`).
"""

from fastapi.routing import APIRoute, iter_route_contexts
from httpx import AsyncClient
from uuid_utils.compat import uuid7

from app.modules.spaces.models import Space
from app.web.public import create_public_app

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

# (method, template, guard)
ROUTES: list[tuple[str, str, str]] = [
    ("POST", "/api/auth/login", "public"),
    ("POST", "/api/auth/logout", "public"),
    ("GET", "/api/auth/me", "session"),
    ("PATCH", "/api/auth/me", "session"),
    ("POST", "/api/auth/me/password", "session"),
    ("GET", "/api/directory", "session"),
    ("GET", "/api/spaces", "session"),
    ("POST", "/api/spaces", "session"),
    ("GET", "/api/spaces/{space_id}", "space"),
    ("PATCH", "/api/spaces/{space_id}", "space"),
    ("GET", "/api/spaces/{space_id}/members", "space"),
    ("PUT", "/api/spaces/{space_id}/members", "space"),
    ("DELETE", "/api/spaces/{space_id}/members/{member_type}/{member_id}", "space"),
    ("GET", "/api/admin/audit", "admin"),
    ("GET", "/api/admin/users", "admin"),
    ("POST", "/api/admin/users", "admin"),
    ("PATCH", "/api/admin/users/{user_id}", "admin"),
    ("POST", "/api/admin/users/{user_id}/deactivate", "admin"),
    ("POST", "/api/admin/users/{user_id}/reactivate", "admin"),
    ("GET", "/api/admin/groups", "admin"),
    ("POST", "/api/admin/groups", "admin"),
    ("GET", "/api/admin/groups/{group_id}", "admin"),
    ("PATCH", "/api/admin/groups/{group_id}", "admin"),
    ("DELETE", "/api/admin/groups/{group_id}", "admin"),
    ("GET", "/api/admin/groups/{group_id}/members", "admin"),
    ("POST", "/api/admin/groups/{group_id}/members", "admin"),
    ("DELETE", "/api/admin/groups/{group_id}/members/{member_type}/{member_id}", "admin"),
]


def _api_routes() -> set[tuple[str, str]]:
    found = set()
    for context in iter_route_contexts(create_public_app().routes):
        route = context.original_route
        path = context.path
        if isinstance(route, APIRoute) and path.startswith("/api") and "/_test" not in path:
            found |= {(method, path) for method in route.methods}
    return found


def _concrete(template: str, space_id: object | None = None) -> str:
    ids = {
        "{space_id}": str(space_id or uuid7()),
        "{user_id}": str(uuid7()),
        "{group_id}": str(uuid7()),
        "{member_type}": "user",
        "{member_id}": str(uuid7()),
    }
    for name, value in ids.items():
        template = template.replace(name, value)
    return template


def test_every_api_route_is_listed() -> None:
    assert {(method, template) for method, template, _ in ROUTES} == _api_routes()


async def test_every_route_but_login_needs_a_session(make_client) -> None:
    anonymous = await make_client(csrf=True)
    for method, template, guard in ROUTES:
        if guard == "public":
            continue
        response = await anonymous.request(method, _concrete(template), json={})
        assert response.status_code == 401, (method, template, response.text)


async def test_every_unsafe_route_needs_the_csrf_header(make_client) -> None:
    no_header = await make_client()
    for method, template, _ in ROUTES:
        if method in UNSAFE:
            response = await no_header.request(method, _concrete(template), json={})
            assert response.status_code == 403, (method, template)
            assert response.json()["error"]["code"] == "auth.csrf"


async def test_space_routes_hide_spaces_without_a_role(
    member_client: AsyncClient, team_space: Space
) -> None:
    bodies = {
        "PATCH": {"name": "X", "version": team_space.version},
        "PUT": {"member_type": "user", "member_id": str(uuid7()), "role": "viewer"},
    }
    for method, template, guard in ROUTES:
        if guard == "space":
            path = _concrete(template, team_space.id)
            response = await member_client.request(method, path, json=bodies.get(method))
            assert response.status_code == 404, (method, template, response.text)
