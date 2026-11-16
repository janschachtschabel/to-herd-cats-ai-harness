"""S3 fixtures (plan M9 task 14): `s3_stub` (a local S3-compatible store over http,
reset per test), `s3_settings_for` (settings pointing at it) and `s3_storage` (the
app's settings switched to S3 for one test, so the API, the backup and the due loop
use the stub)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from tests.support.s3_stub import ACCESS_KEY, BUCKET, SECRET_KEY, S3Stub


@pytest.fixture(scope="session")
def _s3_stub() -> Iterator[S3Stub]:
    stub = S3Stub().start()
    yield stub
    stub.stop()


@pytest.fixture
def s3_stub(_s3_stub: S3Stub) -> Iterator[S3Stub]:
    _s3_stub.state.reset()
    yield _s3_stub
    _s3_stub.state.reset()


def s3_values(stub: S3Stub, **changes: Any) -> dict[str, Any]:
    return {
        "storage": "s3",
        "s3_endpoint": stub.url,
        "s3_bucket": BUCKET,
        "s3_access_key_id": ACCESS_KEY,
        "s3_secret_access_key": SecretStr(SECRET_KEY),
        **changes,
    }


def s3_settings_for(stub: S3Stub, base: Settings | None = None, **changes: Any) -> Settings:
    """`base` (or fresh settings) with the store pointing at the stub, validated."""
    values = (base or Settings()).model_dump() | s3_values(stub, **changes)
    return Settings.model_validate(values)


@pytest.fixture
def s3_storage(
    s3_stub: S3Stub, monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> Iterator[S3Stub]:
    """The app's own settings on S3 for this test (local files: none)."""
    settings = get_settings()
    configured = s3_settings_for(s3_stub)
    for name in ("storage", "s3_endpoint", "s3_bucket", "s3_access_key_id"):
        monkeypatch.setattr(settings, name, getattr(configured, name))
    monkeypatch.setattr(settings, "s3_secret_access_key", configured.s3_secret_access_key)
    yield s3_stub
