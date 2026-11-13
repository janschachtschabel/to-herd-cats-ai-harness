from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.web.public import create_public_app


async def test_app_error_has_code_message_and_trace_id(client):
    r = await client.get("/api/_test/not-found")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "test.not_found"
    assert len(body["trace_id"]) == 32


async def test_unhandled_exception_is_500_with_generic_message(client):
    r = await client.get("/api/_test/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal"
    assert "boom" not in r.text


async def test_validation_error_uses_error_shape(client):
    r = await client.get("/api/_test/needs-int?n=abc")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"
    assert len(r.json()["error"]["trace_id"]) == 32


async def test_openapi_served_under_api_prefix(client):
    assert (await client.get("/api/openapi.json")).status_code == 200
    assert (await client.get("/api/docs")).status_code == 200


async def test_swagger_ui_is_not_served_in_production() -> None:
    """Swagger UI loads its assets from a CDN: no third-party requests in production.
    The OpenAPI document itself stays."""
    app = create_public_app(Settings(environment="production"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/docs")).status_code == 404
        assert (await c.get("/api/openapi.json")).status_code == 200
