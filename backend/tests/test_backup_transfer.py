"""Downloading and uploading archives in the administration (plan M9 task 13): a
download streams the file and is audited; an upload is bounded by
HERD_BACKUP_UPLOAD_MAX_BYTES, read back like a backup, and kept only when good."""

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.ops.archive import read_sidecar, sidecar_of, verify_archive
from tests.factories import login
from tests.factories_restore import make_archive, source_settings
from tests.real_db import MakeRealClient, RealDb


@pytest.fixture
async def archive(real_db: RealDb, tmp_path: Path, data_dir: Path) -> Path:
    path = await make_archive(source_settings(tmp_path, data_dir))
    return path


@pytest.fixture
def backups(archive: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "backup_dir", archive.parent)
    return archive.parent


def _read(path: Path) -> bytes:
    return path.read_bytes()


def _size(path: Path) -> int:
    return path.stat().st_size


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _names(directory: Path) -> set[Path]:
    return set(directory.iterdir())


async def _audit(real_db: RealDb, action: str) -> list[AuditLog]:
    async with real_db.database.session_factory() as session:
        rows = await session.scalars(select(AuditLog).where(AuditLog.action == action))
        return list(rows.all())


async def test_download_streams_and_audits(  # type: ignore[no-untyped-def]
    real_db: RealDb, make_real_client: MakeRealClient, archive: Path, backups: Path
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    response = await owner.get(f"/api/backups/archives/{archive.name}")
    assert response.status_code == 200
    assert response.content == _read(archive)
    assert response.headers["content-type"] == "application/x-tar"
    assert response.headers["content-length"] == str(_size(archive))
    assert response.headers["content-disposition"].startswith(
        f'attachment; filename="{archive.name}"'
    )
    assert response.headers["cache-control"] == "private, no-store"
    (entry,) = await _audit(real_db, "backup.downloaded")
    assert entry.actor_type == "user"
    assert entry.details == {"archive": archive.name, "bytes": _size(archive)}

    (backups / "secret.txt").write_text("not served")
    (backups / "herd-20990101T000000Z-1.0.0.tar").symlink_to(backups / "secret.txt")
    for name in (
        "secret.txt",
        "herd-20990101T000000Z-1.0.0.tar",
        "herd-20261115T023007Z-1.0.0.manifest.json",
        "herd-20990101T000000Z-missing.tar",
    ):
        refused = await owner.get(f"/api/backups/archives/{name}")
        assert refused.status_code == 404, name
        assert refused.json()["error"]["code"] == "backup.not_found"
    climbing = await owner.get("/api/backups/archives/..%2Fsecret.txt")
    assert climbing.status_code == 404 and b"not served" not in climbing.content
    assert len(await _audit(real_db, "backup.downloaded")) == 1


async def test_upload_is_bounded_and_checked(  # type: ignore[no-untyped-def]
    real_db: RealDb,
    make_real_client: MakeRealClient,
    archive: Path,
    backups: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    data = _read(archive)
    before = _names(backups)

    uploaded = await owner.post(
        "/api/backups/archives", content=data, headers={"Content-Type": "application/x-tar"}
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["name"].startswith("upload-") and body["name"].endswith(".tar")
    assert (body["bytes"], body["uploaded"]) == (len(data), True)
    stored = backups / body["name"]
    assert _read(stored) == data
    assert _mode(stored) == 0o600
    _, sha = read_sidecar(stored)
    assert sha == hashlib.sha256(data).hexdigest()
    assert verify_archive(stored) == []
    (entry,) = await _audit(real_db, "backup.uploaded")
    assert entry.details == {"archive": body["name"], "bytes": len(data)}
    listed = (await owner.get("/api/backups/archives")).json()["items"]
    assert {item["name"] for item in listed} == {archive.name, body["name"]}
    known = _names(backups)

    tampered = bytearray(data)
    tampered[2000] ^= 0xFF  # inside the dump
    for content, problem in ((bytes(tampered), "archive.member_checksum"), (b"x" * 4096, None)):
        refused = await owner.post("/api/backups/archives", content=content)
        assert refused.status_code == 422, refused.text
        error = refused.json()["error"]
        assert error["code"] == "backup.archive_invalid"
        if problem:
            assert problem in error["details"]["problems"]
        assert _names(backups) == known  # nothing left, no .part

    monkeypatch.setattr(get_settings(), "backup_upload_max_bytes", len(data) - 1)
    too_large = await owner.post("/api/backups/archives", content=data)
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "backup.upload_too_large"
    assert _names(backups) == known
    assert len(await _audit(real_db, "backup.uploaded")) == 1
    assert before < known and json.loads(_read(sidecar_of(stored)))["format"] == 1


def test_an_upload_has_its_own_body_limit() -> None:
    from app.core.body_limit import BodyLimitMiddleware
    from app.core.config import Settings
    from app.web.public import body_limits

    settings = Settings(backup_upload_max_bytes=7 * 1024**3)
    middleware = BodyLimitMiddleware(
        lambda *_: None,  # type: ignore[arg-type,return-value]
        max_bytes=1024,
        routes=body_limits(settings),
    )
    upload = {"method": "POST", "path": "/api/backups/archives"}
    assert middleware.limit_for(upload) == 7 * 1024**3
    assert middleware.limit_for({"method": "POST", "path": "/api/backups"}) == 1024
    check = {"method": "POST", "path": "/api/backups/archives/x.tar/check"}
    assert middleware.limit_for(check) == 1024
