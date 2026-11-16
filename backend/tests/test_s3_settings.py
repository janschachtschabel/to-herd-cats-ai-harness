"""The S3 settings (plan M9 task 14): what `HERD_STORAGE=s3` needs, the secret key as
a value or a file, and the secret never in a repr, an error, a log line or a request
other than as a signature."""

import hashlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.storage import StorageUnavailable, get_storage
from tests.factories_s3 import s3_values
from tests.support.s3_stub import SECRET_KEY, S3Stub

SECRET = "s3-secret-that-must-never-show-0123"


def _settings(stub: S3Stub, **changes: object) -> Settings:
    return Settings(**s3_values(stub, **changes))


def test_local_storage_needs_nothing() -> None:
    settings = Settings(storage="local")
    assert settings.storage == "local" and settings.s3_endpoint == ""


@pytest.mark.parametrize(
    ("changes", "named"),
    [
        ({"s3_endpoint": ""}, "HERD_S3_ENDPOINT"),
        ({"s3_endpoint": "ftp://store"}, "HERD_S3_ENDPOINT"),
        ({"s3_endpoint": "https://key:secret@store"}, "HERD_S3_ENDPOINT"),
        ({"s3_endpoint": "https://store/bucket"}, "HERD_S3_ENDPOINT"),
        ({"s3_endpoint": "https://store?x=1"}, "HERD_S3_ENDPOINT"),
        ({"s3_bucket": ""}, "HERD_S3_BUCKET"),
        ({"s3_bucket": "Upper"}, "HERD_S3_BUCKET"),
        ({"s3_region": "eu central"}, "HERD_S3_REGION"),
        ({"s3_access_key_id": ""}, "HERD_S3_ACCESS_KEY_ID"),
        ({"s3_secret_access_key": None}, "HERD_S3_SECRET_ACCESS_KEY"),
        ({"s3_secret_access_key": ""}, "HERD_S3_SECRET_ACCESS_KEY"),
        ({"s3_prefix": "Bad Prefix"}, "HERD_S3_PREFIX"),
    ],
)
def test_s3_settings_are_refused_by_name(
    s3_stub: S3Stub, changes: dict[str, object], named: str
) -> None:
    with pytest.raises(ValidationError) as refused:
        _settings(s3_stub, **changes)
    assert named in str(refused.value)


def test_the_secret_key_can_come_from_a_file(s3_stub: S3Stub, tmp_path: Path) -> None:
    file = tmp_path / "s3-secret"
    file.write_text(f"{SECRET_KEY}\n")
    settings = _settings(s3_stub, s3_secret_access_key=None, s3_secret_access_key_file=file)
    assert settings.s3_credentials().secret_access_key == SECRET_KEY
    with pytest.raises(ValidationError, match="not both"):
        _settings(s3_stub, s3_secret_access_key_file=file)
    file.write_text("\n")
    with pytest.raises(ValidationError, match="empty"):
        _settings(s3_stub, s3_secret_access_key=None, s3_secret_access_key_file=file)


def test_the_prefix_is_normalised(s3_stub: S3Stub) -> None:
    assert _settings(s3_stub, s3_prefix="/herd/prod/").s3_prefix == "herd/prod"


async def _one(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def test_no_s3_secret_in_logs_or_errors(
    s3_stub: S3Stub, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    caplog.set_level(logging.DEBUG)
    settings = _settings(s3_stub, s3_secret_access_key=SecretStr(SECRET))
    assert SECRET not in repr(settings) and SECRET not in str(settings.model_dump())
    assert SECRET not in repr(settings.s3_credentials())
    storage = get_storage(settings)
    failures: list[str] = []
    one = hashlib.sha256(b"a").hexdigest()
    attempts = (
        storage.exists("attachments/x"),
        storage.put("attachments/x", _one(b"a"), size=1, sha256=one),
    )
    for attempt in attempts:
        with pytest.raises(StorageUnavailable) as failed:
            await attempt
        failures += [str(failed.value), repr(failed.value), failed.value.reason]
    with pytest.raises(ValidationError) as refused:
        Settings(**s3_values(s3_stub, s3_secret_access_key=SecretStr(SECRET), s3_bucket="X"))
    failures.append(str(refused.value))
    assert all(SECRET not in text for text in failures)
    assert SECRET not in caplog.text
    assert any(r.getMessage() == "storage.s3_failed" for r in caplog.records)
    for entry in s3_stub.state.log:  # only the signature travels, never the key
        values = (entry.path, entry.query, *entry.headers.values())
        assert all(SECRET not in value for value in values)
