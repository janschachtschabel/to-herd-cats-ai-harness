"""The manifest of a backup archive (plan M9 decision 3): figures only, never
content. It travels twice: as the archive's last member (`herd/manifest.json`, with the
SHA-256 and size of every other member) and as a sidecar next to the archive
(`<name>.manifest.json`, the same plus `archive_sha256`).

`from_json` is strict: a missing field, an unknown one or a value of the wrong type is
`ManifestInvalid`, so an archive of another format is refused, not half understood.
"""

import json
from datetime import UTC, datetime
from typing import TypedDict

from pydantic import ConfigDict, TypeAdapter, ValidationError
from pydantic.dataclasses import dataclass

FORMAT = 1
CREATED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ManifestInvalid(ValueError):  # noqa: N818 (a state of the input)
    """Not a manifest of this format."""


class Member(TypedDict):
    sha256: str
    size: int


@dataclass(frozen=True, config=ConfigDict(extra="forbid", strict=True))
class Manifest:
    format: int
    app_version: str
    alembic_revision: str
    created_at: str  # UTC, ISO 8601 with Z
    server_major: int
    pg_dump_version: str
    storage: str  # local | s3
    tables: dict[str, int]  # rows per table, in the snapshot
    files: dict[str, int]  # {"count": n, "bytes": n}
    members: dict[str, Member]  # archive member (below herd/) -> checksum and size
    key_id: str | None  # of HERD_SECRET_KEY (`core.secrets.key_id`), never the key
    enc_values: dict[str, int]  # "table.column" -> how many `enc:` values
    env_refs: list[str]  # names of the `env:` references, sorted

    def created(self) -> datetime:
        """`created_at` as a time (whole seconds; ValueError if it is not one)."""
        return datetime.strptime(self.created_at, CREATED_AT_FORMAT).replace(tzinfo=UTC)

    def to_json(self) -> bytes:
        data = _ADAPTER.dump_python(self, mode="json")
        return json.dumps(data, sort_keys=True, indent=2).encode() + b"\n"

    @classmethod
    def from_json(cls, data: bytes) -> "Manifest":
        try:
            return _ADAPTER.validate_json(data)
        except ValidationError:
            raise ManifestInvalid("not a manifest of this format") from None


_ADAPTER = TypeAdapter(Manifest)
