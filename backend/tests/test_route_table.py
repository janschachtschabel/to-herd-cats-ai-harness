"""Every `/api` route is in the table of `tests/route_table.py` with the guard it needs,
and the session and CSRF guards hold (the others: `test_route_hiding.py`). A new route
that is not listed fails `test_every_api_route_is_listed`, so it cannot ship without a
decision on who may call it."""

from fastapi.routing import APIRoute, iter_route_contexts

from app.web.public import create_public_app
from tests.route_table import ROUTES, UNSAFE, concrete


def _api_routes() -> set[tuple[str, str]]:
    found = set()
    for context in iter_route_contexts(create_public_app().routes):
        route = context.original_route
        path = context.path
        if isinstance(route, APIRoute) and path.startswith("/api") and "/_test" not in path:
            found |= {(method, path) for method in route.methods}
    return found


def test_every_api_route_is_listed() -> None:
    assert {(method, template) for method, template, _ in ROUTES} == _api_routes()


async def test_every_route_but_login_needs_a_session(make_client) -> None:
    anonymous = await make_client(csrf=True)
    for method, template, guard in ROUTES:
        if guard == "public":
            continue
        response = await anonymous.request(method, concrete(template), json={})
        assert response.status_code == 401, (method, template, response.text)


async def test_every_unsafe_route_needs_the_csrf_header(make_client) -> None:
    no_header = await make_client()
    for method, template, _ in ROUTES:
        if method in UNSAFE:
            response = await no_header.request(method, concrete(template), json={})
            assert response.status_code == 403, (method, template)
            assert response.json()["error"]["code"] == "auth.csrf"
