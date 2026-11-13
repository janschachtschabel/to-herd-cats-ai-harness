"""Every response of the public app carries the security headers, API and errors too."""

from httpx import ASGITransport, AsyncClient

from app.web.public import create_public_app

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
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert _has_headers(response)
