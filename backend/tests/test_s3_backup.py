"""Backups and restores with attachments in S3 (plan M9 task 14): the archive takes the
files from the object store and a restore puts them back there (or into a local
directory, and a local archive into S3); a store that does not answer fails the backup
with a code, and a key stored with other content refuses the restore."""

import hashlib
import tarfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.storage import get_storage
from app.modules.backups.models import BackupState, BackupTrigger
from app.ops.archive import read_sidecar
from app.ops.backup import create_backup
from app.ops.restore import RestoreRefused, restore_into_empty
from app.ops.restore_checks import check_restore
from tests.factories import login
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.factories_s3 import s3_settings_for
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.support.s3_stub import S3Stub
from tests.test_wiki_attachment_commit import PDF, PNG, _page_with


async def _attachments(real_db: RealDb, make_real_client: MakeRealClient) -> dict[str, str]:
    """Two attachments uploaded through the API: their keys and SHA-256."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, attachments = await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF))
    org = str(real_db.org_id)
    return {f"attachments/{org}/{a['sha256']}": a["sha256"] for a in attachments}


def _on_s3(stub: S3Stub, settings: Settings, prefix: str = "") -> Settings:
    return s3_settings_for(stub, base=settings, s3_prefix=prefix)


def _objects(stub: S3Stub, prefix: str) -> dict[str, str]:
    return {
        k.removeprefix(prefix): hashlib.sha256(o.data).hexdigest()
        for k, o in stub.state.objects.items()
        if k.startswith(prefix)
    }


async def test_backup_and_restore_with_s3(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_storage: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    files = await _attachments(real_db, make_real_client)
    assert _objects(s3_storage, "") == files
    source = _on_s3(s3_storage, source_settings(tmp_path, data_dir))
    archive = await make_archive(source)
    manifest, _ = read_sidecar(archive)
    assert manifest.storage == "s3"
    with tarfile.open(archive) as tar:
        names = {n.removeprefix("herd/files/") for n in tar.getnames() if "/files/" in n}
    assert names == set(files)

    report = await restore_into_empty(
        _on_s3(s3_storage, target.settings, "restored"),
        archive,
        without_secrets=False,
        clock=SettableClock(AT),
    )
    assert report.files == 2
    assert _objects(s3_storage, "restored/") == files
    assert target.files() == {}  # nothing in the local directory


async def test_an_s3_archive_restores_into_a_local_directory_and_back(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_storage: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    files = await _attachments(real_db, make_real_client)
    archive = await make_archive(_on_s3(s3_storage, source_settings(tmp_path, data_dir)))
    await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    assert target.files() == files


async def test_a_local_archive_restores_into_s3(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_stub: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    files = await _attachments(real_db, make_real_client)  # local: the app's own settings
    archive = await make_archive(source_settings(tmp_path, data_dir))
    assert read_sidecar(archive)[0].storage == "local"
    await restore_into_empty(
        _on_s3(s3_stub, target.settings, "moved"),
        archive,
        without_secrets=False,
        clock=SettableClock(AT),
    )
    assert _objects(s3_stub, "moved/") == files


async def test_a_backup_fails_when_the_store_does_not_answer(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_storage: S3Stub,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    await _attachments(real_db, make_real_client)
    s3_storage.state.failures.extend([500] * 4)
    source = _on_s3(s3_storage, source_settings(tmp_path, data_dir))
    outcome = await create_backup(source, trigger=BackupTrigger.CLI, clock=SettableClock(AT))
    assert (outcome.state, outcome.error_code, outcome.archive) == (
        BackupState.FAILED,
        "backup.storage_unavailable",
        None,
    )
    assert list(source.backup_dir.glob("*.tar")) == []


async def _one(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def test_an_object_with_other_content_refuses_the_restore(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_storage: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    files = await _attachments(real_db, make_real_client)
    archive = await make_archive(_on_s3(s3_storage, source_settings(tmp_path, data_dir)))
    destination = _on_s3(s3_storage, target.settings, "taken")
    key = next(iter(files))
    other = b"other bytes under the same key"
    await get_storage(destination).put(
        key, _one(other), size=len(other), sha256=hashlib.sha256(other).hexdigest()
    )
    check = await check_restore(destination, archive)
    assert check.problems == ["restore.file_conflict"]
    before = dict(s3_storage.state.objects)
    with pytest.raises(RestoreRefused):
        await restore_into_empty(
            destination, archive, without_secrets=False, clock=SettableClock(AT)
        )
    assert s3_storage.state.objects == before
    assert await target.tables() == {}


async def test_a_store_that_does_not_answer_refuses_the_check(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_storage: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    await _attachments(real_db, make_real_client)
    archive = await make_archive(_on_s3(s3_storage, source_settings(tmp_path, data_dir)))
    destination = _on_s3(s3_storage, target.settings, "down")
    s3_storage.state.failures.extend([503] * 10)
    check = await check_restore(destination, archive)
    assert "restore.storage_unavailable" in check.problems
