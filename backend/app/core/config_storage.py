"""Where attachments live (plan M9 decision 18): the local directory or an
S3-compatible object store. A part of `Settings` (`config.py` inherits it);
`get_settings()` stays the one source.

The S3 secret key comes from `HERD_S3_SECRET_ACCESS_KEY` or, for mounted secrets,
`HERD_S3_SECRET_ACCESS_KEY_FILE`; `s3_credentials()` is the one reader. Errors name
the setting, never a value.
"""

import re
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings

from app.core.s3_signing import Credentials

_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_PREFIX = re.compile(r"[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*")
_REGION = re.compile(r"[a-z0-9-]{1,32}")


class StorageSettings(BaseSettings):
    # `local`: files under HERD_DATA_DIR (a volume all API replicas share). `s3`: an
    # S3-compatible object store (AWS S3, SeaweedFS, Ceph, Garage, ...), so API pods
    # need no shared volume. Moving: `python -m app.ops storage copy --to s3`.
    storage: Literal["local", "s3"] = "local"
    # The store's address, scheme://host[:port] (https outside a private network);
    # requests are path-style (`<endpoint>/<bucket>/<key>`) and pass the egress guard
    # with this host as its one allowed private target (never metadata addresses).
    s3_endpoint: str = ""
    # The region the store signs for (SeaweedFS and most others accept us-east-1).
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    # The bucket's access key; the secret key as a value or a file (not both).
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr | None = None
    s3_secret_access_key_file: Path | None = None
    # Keys go under this prefix inside the bucket (lower-case segments, `/` between);
    # empty: the bucket's top level.
    s3_prefix: str = ""

    _s3_secret: SecretStr | None = PrivateAttr(default=None)

    @field_validator("s3_secret_access_key_file", mode="before")
    @classmethod
    def _empty_file_is_none(cls, value: object) -> object:
        return None if value == "" else value  # compose: `${...:-}`

    @model_validator(mode="after")
    def _s3_settings_fit(self) -> Self:
        if (
            self.s3_secret_access_key is not None
            and not self.s3_secret_access_key.get_secret_value()
        ):
            self.s3_secret_access_key = None  # compose: `${...:-}`
        self.s3_prefix = self.s3_prefix.strip("/")
        if self.s3_prefix and not _PREFIX.fullmatch(self.s3_prefix):
            raise ValueError("HERD_S3_PREFIX must be lower-case segments separated by /")
        self._s3_secret = _secret(self.s3_secret_access_key, self.s3_secret_access_key_file)
        if self.storage != "s3":
            return self
        _check_endpoint(self.s3_endpoint)
        if not _BUCKET.fullmatch(self.s3_bucket) or ".." in self.s3_bucket:
            raise ValueError("HERD_S3_BUCKET must be a bucket name (3 to 63 of a-z 0-9 . -)")
        if not _REGION.fullmatch(self.s3_region):
            raise ValueError("HERD_S3_REGION must be a region name like us-east-1")
        if not self.s3_access_key_id or self._s3_secret is None:
            raise ValueError(
                "HERD_STORAGE=s3 needs HERD_S3_ACCESS_KEY_ID and "
                "HERD_S3_SECRET_ACCESS_KEY (or HERD_S3_SECRET_ACCESS_KEY_FILE)"
            )
        return self

    def s3_credentials(self) -> Credentials:
        if self._s3_secret is None:
            raise ValueError("HERD_S3_SECRET_ACCESS_KEY is not set")
        return Credentials(self.s3_access_key_id, self._s3_secret.get_secret_value())


def _secret(value: SecretStr | None, file: Path | None) -> SecretStr | None:
    if value is not None and file is not None:
        raise ValueError(
            "set HERD_S3_SECRET_ACCESS_KEY or HERD_S3_SECRET_ACCESS_KEY_FILE, not both"
        )
    if file is None:
        return value
    try:
        content = file.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise ValueError(f"HERD_S3_SECRET_ACCESS_KEY_FILE cannot be read: {exc.strerror}") from None
    if not content:
        raise ValueError("HERD_S3_SECRET_ACCESS_KEY_FILE is empty")
    return SecretStr(content)


def _check_endpoint(endpoint: str) -> None:
    message = "HERD_S3_ENDPOINT must be an http(s) address like https://s3.example:9000"
    try:
        parts = urlsplit(endpoint)
        parts.port  # noqa: B018 (raises on a bad port)
    except ValueError:
        raise ValueError(message) from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or "@" in parts.netloc
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
        or any(c.isspace() for c in endpoint)
    ):
        raise ValueError(message)
