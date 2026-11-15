"""Every response of the public app carries the security headers, API and errors too."""

import re

from fastapi.routing import APIRoute, iter_route_contexts
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.db import get_session
from app.web.public import create_public_app
from tests.app_session import session_override

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}


def _has_headers(response) -> bool:
    return all(response.headers.get(k) == v for k, v in EXPECTED.items())


async def test_api_and_error_responses_carry_security_headers(client: AsyncClient) -> None:
    for method, path in (
        ("GET", "/api/_test/ok"),  # 200 JSON
        ("GET", "/api/auth/me"),  # 401
        ("GET", "/api/_test/nowhere"),  # 404 from routing
        ("GET", "/api/_test/needs-int?n=x"),  # 422
        ("POST", "/api/auth/logout"),  # 403 (CSRF)
        ("GET", "/api/_test/boom"),  # 500
        ("GET", "/api/openapi.json"),
    ):
        response = await client.request(method, path)
        assert _has_headers(response), (path, dict(response.headers))
        assert "strict-transport-security" not in response.headers


async def test_hsts_only_over_https() -> None:
    transport = ASGITransport(app=create_public_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        response = await c.get("/api/_test/ok")
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert _has_headers(response)


def _directives(policy: str) -> dict[str, str]:
    pairs = (d.strip().split(" ", 1) for d in policy.split(";") if d.strip())
    return {p[0]: p[1] if len(p) > 1 else "" for p in pairs}


def _concrete(path: str) -> str:
    """A route template with every parameter filled (an id nobody has)."""
    return re.sub(r"\{[^}]+\}", str(uuid7()), path)


def _public_routes() -> list[tuple[str, str]]:
    found = []
    for context in iter_route_contexts(create_public_app().routes):
        route = context.original_route
        if isinstance(route, APIRoute):
            found += [(method, context.path) for method in sorted(route.methods)]
    return found


async def test_security_headers_on_every_public_route(session: AsyncSession) -> None:
    """ASVS 5.0 V3.4: every answer of the public app, whatever its status, carries a
    Content-Security-Policy with frame-ancestors, object-src and base-uri 'none',
    nosniff, a referrer policy, and behind https an HSTS policy for at least a year that
    covers subdomains."""
    app = create_public_app()
    app.dependency_overrides[get_session] = session_override(session)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    routes = _public_routes() + [("GET", "/api/openapi.json"), ("GET", "/api/nowhere")]
    assert len(routes) > 250  # the walk found the app's routes
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        for method, path in routes:
            response = await c.request(method, _concrete(path))
            where = (method, path, response.status_code)
            assert _has_headers(response), where
            csp = _directives(response.headers.get("content-security-policy", ""))
            for directive in ("frame-ancestors", "object-src", "base-uri"):
                assert csp.get(directive) == "'none'", (where, directive)
            hsts = response.headers.get("strict-transport-security", "")
            assert hsts == "max-age=31536000; includeSubDomains", where


async def test_swagger_ui_outside_production_keeps_working(client: AsyncClient) -> None:
    """Swagger UI loads its scripts from a CDN, so it gets no API policy; production
    serves no Swagger UI at all (`test_swagger_ui_is_not_served_in_production`)."""
    response = await client.get("/api/docs")
    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert _has_headers(response)


async def test_api_answers_are_not_stored_by_browsers(make_client) -> None:
    """ASVS 5.0 V14.3.2: what the API answers (a person's data, errors) is never kept
    in a browser's or proxy's cache; downloads say their own (private, revalidated)."""
    me = await make_client()
    for method, path in (
        ("GET", "/api/_test/ok"),
        ("GET", "/api/auth/me"),
        ("GET", "/api/_test/boom"),
        ("GET", "/api/openapi.json"),
        ("POST", "/mcp"),
    ):
        response = await me.request(method, path)
        assert response.headers.get("cache-control") == "no-store", (path, response.status_code)
