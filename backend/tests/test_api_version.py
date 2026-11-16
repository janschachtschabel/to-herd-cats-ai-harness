"""The public API's OpenAPI document names the application's version (pyproject, the
chart's appVersion and the image tag), not FastAPI's default."""

from app.version import app_version
from app.web.public import create_public_app


def test_the_openapi_document_carries_the_app_version() -> None:
    assert create_public_app().openapi()["info"]["version"] == app_version()
