"""Backup archives (plan M9 decisions 3 and 5): the manifest round-trips and refuses
what it does not know; `verify_archive` finds a changed byte, a missing member and a
truncated tail; the key id names the secret key without giving it away."""

import hashlib
import json
import os
import stat
import tarfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core import secrets
from app.core.config import get_settings
from app.ops.archive import ArchiveWriter, read_sidecar, verify_archive
from app.ops.manifest import Manifest, ManifestInvalid

DUMP = b"PGDMP" + bytes(range(256)) * 40
FILE = b"%PDF-1.7\n" + b"x" * 3000
KEY = "attachments/0190a1b2-0000-7000-8000-000000000001/" + hashlib.sha256(FILE).hexdigest()


def _manifest(**changes: object) -> Manifest:
    values: dict[str, object] = {
        "format": 1,
        "app_version": "0.1.0",
        "alembic_revision": "8e2a4c6b0d1f",
        "created_at": "2026-11-15T02:30:00Z",
        "server_major": 16,
        "pg_dump_version": "16.15",
        "storage": "local",
        "tables": {"page": 3, "attachment": 1},
        "files": {"count": 1, "bytes": len(FILE)},
        "members": {},
        "key_id": "0123456789abcdef",
        "enc_values": {"ai_connection.secret_ref": 2},
        "env_refs": ["HERD_AI_OPENAI"],
    }
    values.update(changes)
    return Manifest(**values)  # type: ignore[arg-type]


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(data), 1000):
        yield data[start : start + 1000]


async def _archive(tmp_path: Path) -> Path:
    path = tmp_path / "out" / "herd-20261115T023000Z-0.1.0.tar"
    writer = ArchiveWriter(path)
    dump = tmp_path / "db.dump"
    dump.write_bytes(DUMP)
    await writer.add_file("db.dump", dump)
    await writer.add_stream(f"files/{KEY}", len(FILE), _chunks(FILE))
    await writer.finish(_manifest())
    return path


def test_manifest_round_trips_and_refuses_unknown_fields() -> None:
    manifest = _manifest(members={"db.dump": {"sha256": "ab" * 32, "size": 12}})
    assert Manifest.from_json(manifest.to_json()) == manifest
    data = json.loads(manifest.to_json())
    data["surprise"] = 1
    with pytest.raises(ManifestInvalid):
        Manifest.from_json(json.dumps(data).encode())
    del data["surprise"]
    del data["tables"]
    with pytest.raises(ManifestInvalid):
        Manifest.from_json(json.dumps(data).encode())
    data["tables"] = {"page": "three"}
    with pytest.raises(ManifestInvalid):
        Manifest.from_json(json.dumps(data).encode())
    with pytest.raises(ManifestInvalid):
        Manifest.from_json(b"not json")


@pytest.mark.parametrize(
    "changes",
    [
        {"pg_dump_version": "sixteen"},
        {"pg_dump_version": "16.15 (Ubuntu)"},
        {"created_at": "yesterday"},
        {"created_at": "2026-11-15 02:30:00"},
    ],
    ids=str,
)
def test_manifest_refuses_values_of_the_wrong_form(changes: dict[str, object]) -> None:
    """Review M9b F6: the check and the replace read both as a number and a time."""
    data = json.loads(_manifest().to_json())
    data.update(changes)
    with pytest.raises(ManifestInvalid):
        Manifest.from_json(json.dumps(data).encode())
    assert Manifest.from_json(_manifest(pg_dump_version="17").to_json()).tools_major() == 17


async def test_an_archive_holds_its_members_in_order_with_their_checksums(
    tmp_path: Path,
) -> None:
    path = await _archive(tmp_path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    with tarfile.open(path) as tar:
        names = tar.getnames()
        assert names == ["herd/FORMAT", "herd/db.dump", f"herd/files/{KEY}", "herd/manifest.json"]
        member = tar.extractfile(f"herd/files/{KEY}")
        assert member is not None and member.read() == FILE
        inner = tar.extractfile("herd/manifest.json")
        assert inner is not None
        manifest = Manifest.from_json(inner.read())
    assert manifest.members["db.dump"] == {
        "sha256": hashlib.sha256(DUMP).hexdigest(),
        "size": len(DUMP),
    }
    assert manifest.members[f"files/{KEY}"]["sha256"] == hashlib.sha256(FILE).hexdigest()
    side, archive_sha256 = read_sidecar(path)
    assert side == manifest
    assert archive_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert verify_archive(path) == []


async def test_verify_finds_a_changed_byte_a_missing_member_and_a_truncated_tail(
    tmp_path: Path,
) -> None:
    path = await _archive(tmp_path)
    data = path.read_bytes()

    changed = bytearray(data)
    changed[data.index(FILE) + 100] ^= 0xFF  # inside the attachment's data
    path.write_bytes(bytes(changed))
    assert verify_archive(path) == ["archive.checksum", "archive.member_checksum"]

    path.write_bytes(data[: data.index(FILE) + 2000])
    assert "archive.truncated" in verify_archive(path)

    # The archive without its attachment member, with a sidecar that fits the new file.
    with tarfile.open(tmp_path / "copy.tar", "w", format=tarfile.PAX_FORMAT) as out:
        path.write_bytes(data)
        with tarfile.open(path) as tar:
            for info in tar.getmembers():
                if info.name != f"herd/files/{KEY}":
                    out.addfile(info, tar.extractfile(info))
    os.replace(tmp_path / "copy.tar", path)
    _rewrite_sidecar(path)
    assert verify_archive(path) == ["archive.member_missing"]


async def test_verify_refuses_an_unknown_format(tmp_path: Path) -> None:
    path = await _archive(tmp_path)
    data = path.read_bytes()
    with tarfile.open(path) as tar:
        offset = tar.getmember("herd/FORMAT").offset_data
    changed = bytearray(data)
    changed[offset] = ord("2")
    path.write_bytes(bytes(changed))
    _rewrite_sidecar(path)
    assert verify_archive(path) == ["archive.format_unknown"]


async def test_an_archive_without_its_sidecar_is_checked_by_its_members(tmp_path: Path) -> None:
    path = await _archive(tmp_path)
    path.with_name(path.name.removesuffix(".tar") + ".manifest.json").unlink()
    assert verify_archive(path) == []


def _rewrite_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name.removesuffix(".tar") + ".manifest.json")
    data = json.loads(sidecar.read_bytes())
    data["archive_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar.write_text(json.dumps(data))


def test_key_id_is_stable_and_never_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key, previous = "k" * 40, "p" * 40
    first = secrets.key_id(key)
    assert first == secrets.key_id(key)
    assert len(first) == 16 and int(first, 16) >= 0
    assert first != secrets.key_id(previous)
    assert key[:16] not in first
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(key))
    monkeypatch.setattr(get_settings(), "secret_key_previous", SecretStr(previous))
    assert secrets.current_key_ids() == (first, secrets.key_id(previous))
    monkeypatch.setattr(get_settings(), "secret_key", None)
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)
    assert secrets.current_key_ids() == (None, None)
