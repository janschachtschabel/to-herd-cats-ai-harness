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
- `page`: a role in the page's space; a member without a role in a team space gets
  404 `page.not_found`, as for an unknown page.
- `conversation`: whoever may see the conversation (a channel: its space); a member
  without a role in a team space gets 404 `conversation.not_found`.
- `message`: whoever may see the message's conversation; otherwise 404
  `message.not_found`.
Every unsafe method also needs the CSRF header (→ 403 `auth.csrf`).
"""

from fastapi.routing import APIRoute, iter_route_contexts
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.principal import Principal, SystemRole
from app.modules.messaging.channels import ChannelService
from app.modules.messaging.service import MessageService
from app.modules.spaces.models import Space
from app.modules.users.models import User
from app.modules.wiki.service import PageService
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
    ("GET", "/api/spaces/{space_id}/pages/tree", "space"),
    ("POST", "/api/spaces/{space_id}/pages", "space"),
    ("GET", "/api/spaces/{space_id}/pages/by-path", "space"),
    ("GET", "/api/pages/{page_id}", "page"),
    ("PATCH", "/api/pages/{page_id}", "page"),
    ("POST", "/api/pages/{page_id}/publish", "page"),
    ("POST", "/api/pages/{page_id}/move", "page"),
    ("POST", "/api/pages/{page_id}/trash", "page"),
    ("POST", "/api/pages/{page_id}/restore", "page"),
    ("GET", "/api/spaces/{space_id}/trash", "space"),
    ("DELETE", "/api/pages/{page_id}", "admin"),  # purge: page.purge (system admins)
    ("GET", "/api/pages/{page_id}/versions", "page"),
    ("GET", "/api/pages/{page_id}/versions/{number}", "page"),
    ("PATCH", "/api/pages/{page_id}/versions/{number}", "page"),
    ("POST", "/api/pages/{page_id}/versions/{number}/restore", "page"),
    ("GET", "/api/pages/{page_id}/diff", "page"),
    ("PUT", "/api/pages/{page_id}/tags", "page"),
    ("POST", "/api/pages/{page_id}/attachments", "page"),
    ("GET", "/api/pages/{page_id}/attachments", "page"),
    ("GET", "/api/attachments/{attachment_id}", "session"),
    ("DELETE", "/api/attachments/{attachment_id}", "session"),
    ("POST", "/api/spaces/{space_id}/import", "space"),
    ("GET", "/api/spaces/{space_id}/export", "space"),
    ("GET", "/api/pages/{page_id}/export", "page"),
    ("GET", "/api/tags", "session"),
    ("GET", "/api/search", "session"),
    ("POST", "/api/tags", "session"),  # system tags: tag.manage; space tags: page.moderate
    ("PATCH", "/api/tags/{tag_id}", "session"),
    ("DELETE", "/api/tags/{tag_id}", "session"),
    ("GET", "/api/spaces/{space_id}/channels", "space"),
    ("POST", "/api/spaces/{space_id}/channels", "space"),
    ("GET", "/api/channels", "session"),
    ("GET", "/api/conversations/{conversation_id}", "conversation"),
    ("PATCH", "/api/conversations/{conversation_id}", "conversation"),
    ("POST", "/api/conversations/{conversation_id}/archive", "conversation"),
    ("POST", "/api/conversations/{conversation_id}/unarchive", "conversation"),
    ("GET", "/api/conversations/{conversation_id}/messages", "conversation"),
    ("POST", "/api/conversations/{conversation_id}/messages", "conversation"),
    ("GET", "/api/messages/{message_id}/replies", "message"),
    ("PATCH", "/api/messages/{message_id}", "message"),
    ("DELETE", "/api/messages/{message_id}", "message"),
    ("POST", "/api/dms", "session"),
    ("GET", "/api/dms", "session"),
    ("GET", "/api/admin/dm-inspect", "admin"),
    ("POST", "/api/admin/dm-inspect", "admin"),
    ("GET", "/api/admin/dm-inspect/{inspection_id}/messages", "admin"),
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


def _concrete(
    template: str,
    space_id: object | None = None,
    page_id: object | None = None,
    conversation_id: object | None = None,
    message_id: object | None = None,
) -> str:
    ids = {
        "{message_id}": str(message_id or uuid7()),
        "{conversation_id}": str(conversation_id or uuid7()),
        "{space_id}": str(space_id or uuid7()),
        "{page_id}": str(page_id or uuid7()),
        "{user_id}": str(uuid7()),
        "{group_id}": str(uuid7()),
        "{member_type}": "user",
        "{member_id}": str(uuid7()),
        "{number}": "1",
        "{tag_id}": str(uuid7()),
        "{attachment_id}": str(uuid7()),
        "{inspection_id}": str(uuid7()),
    }
    for name, value in ids.items():
        template = template.replace(name, value)
    queries = {
        "/by-path": "?path=x",
        "/diff": "?from=1&to=1",
        "/attachments": "?filename=x.txt",
        "/dm-inspect": f"?user_id={uuid7()}",
    }
    return template + next((q for end, q in queries.items() if template.endswith(end)), "")


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


# A valid body for every route that takes one, so the guard is what answers.
BODIES: dict[tuple[str, str], dict[str, object]] = {
    ("PATCH", "/api/spaces/{space_id}"): {"name": "X", "version": 1},
    ("PUT", "/api/spaces/{space_id}/members"): {
        "member_type": "user",
        "member_id": str(uuid7()),
        "role": "viewer",
    },
    ("POST", "/api/spaces/{space_id}/pages"): {"title": "X"},
    ("PATCH", "/api/pages/{page_id}"): {"title": "X", "version": 1},
    ("POST", "/api/pages/{page_id}/publish"): {"version": 1},
    ("POST", "/api/pages/{page_id}/move"): {"parent_id": None, "version": 1},
    ("POST", "/api/pages/{page_id}/trash"): {"version": 1},
    ("PATCH", "/api/pages/{page_id}/versions/{number}"): {"label": "X"},
    ("POST", "/api/pages/{page_id}/versions/{number}/restore"): {"version": 1},
    ("PUT", "/api/pages/{page_id}/tags"): {"tag_ids": [], "version": 1},
    ("POST", "/api/spaces/{space_id}/channels"): {"name": "x"},
    ("PATCH", "/api/conversations/{conversation_id}"): {"topic": "x", "version": 1},
    ("POST", "/api/conversations/{conversation_id}/archive"): {"version": 1},
    ("POST", "/api/conversations/{conversation_id}/unarchive"): {"version": 1},
    ("POST", "/api/conversations/{conversation_id}/messages"): {"body_md": "x"},
    ("PATCH", "/api/messages/{message_id}"): {"body_md": "x"},
}


async def test_space_routes_hide_spaces_without_a_role(
    member_client: AsyncClient, team_space: Space
) -> None:
    for method, template, guard in ROUTES:
        if guard == "space":
            path = _concrete(template, team_space.id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "space.not_found"


async def test_page_routes_hide_pages_without_a_role(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    page = await PageService(session).create(actor, team_space.id, None, "Geheim")
    for method, template, guard in ROUTES:
        if guard == "page":
            path = _concrete(template, team_space.id, page.id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "page.not_found"


async def test_conversation_routes_hide_conversations_without_a_role(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    channel = await ChannelService(session).create(actor, team_space.id, "geheim", None)
    message, _ = await MessageService(session).post(actor, channel.id, "Geheim")
    for method, template, guard in ROUTES:
        if guard in ("conversation", "message"):
            path = _concrete(
                template, team_space.id, conversation_id=channel.id, message_id=message.id
            )
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == f"{guard}.not_found"
