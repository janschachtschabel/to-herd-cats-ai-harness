"""Checking an archive and replacing the installation from the administration (plan M9
task 13): the check shows the archive against the installation (versions, revision,
key, rows and files, problems and warnings); replacing needs the organisation's exact
name and a clean check, and runs Task 12's replace in the background with `via` admin.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.audit.recorder import record_system
from app.modules.backups.replacing import replace_runner
from app.ops.restore import RestoreRefused
from app.version import app_version
from tests.factories import login
from tests.factories_restore import (
    KEY,
    OTHER_KEY,
    add_encrypted_connection,
    make_archive,
    source_settings,
)
from tests.real_db import MakeRealClient, RealDb


def _flip(path: Path, offset: int) -> None:
    data = bytearray(path.read_bytes())
    data[offset] ^= 0xFF
    path.write_bytes(bytes(data))


async def _audit(real_db: RealDb, action: str) -> list[AuditLog]:
    async with real_db.database.session_factory() as session:
        rows = await session.scalars(select(AuditLog).where(AuditLog.action == action))
        return list(rows.all())


@pytest.fixture
async def archive(
    real_db: RealDb, tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    await add_encrypted_connection(real_db, monkeypatch)  # an `enc:` value under KEY
    path = await make_archive(source_settings(tmp_path, data_dir))
    monkeypatch.setattr(get_settings(), "backup_dir", path.parent)
    return path


async def test_the_check_shows_the_archive_against_the_installation(  # type: ignore[no-untyped-def]
    real_db: RealDb,
    make_real_client: MakeRealClient,
    archive: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    good = (await owner.post(f"/api/backups/archives/{archive.name}/check")).json()
    assert (good["problems"], good["key"], good["can_replace"]) == ([], "match", True)
    assert good["archive_name"] == archive.name
    theirs, ours = good["archive"], good["installation"]
    assert theirs["app_version"] == ours["app_version"] == app_version()
    assert theirs["alembic_revision"] == ours["alembic_revision"]
    assert theirs["server_major"] == ours["server_major"] >= 16
    assert theirs["tools_major"] is not None and ours["tools_major"] is not None
    assert theirs["tables"] == ours["tables"] > 50
    assert theirs["rows"] > 0 and theirs["files"] == ours["files"] == 0
    assert good["created_at"] == "2026-11-15T02:30:07Z"

    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(OTHER_KEY))
    wrong = (await owner.post(f"/api/backups/archives/{archive.name}/check")).json()
    assert wrong["key"] == "mismatch" and wrong["can_replace"] is False
    assert wrong["problems"] == ["restore.secret_key_mismatch"]
    assert "restore.secrets_unreadable:ai_connection.secret_ref=1" in wrong["warnings"]

    _flip(archive, 2000)
    broken = (await owner.post(f"/api/backups/archives/{archive.name}/check")).json()
    assert "archive.checksum" in broken["problems"] and broken["can_replace"] is False
    assert (broken["archive"], broken["installation"], broken["key"]) == (None, None, None)
    audited = [entry.details for entry in await _audit(real_db, "backup.checked")]
    assert [d["problems"] for d in audited if d is not None] == [
        [],
        ["restore.secret_key_mismatch"],
        broken["problems"],
    ]


class FakeReplace:
    def __init__(self, refuse: list[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.refuse = refuse

    async def __call__(self, settings: Any, archive: Path, **kwargs: Any) -> None:
        self.calls.append({"archive": archive, **kwargs})
        if self.refuse:
            raise RestoreRefused(self.refuse)


async def _settled() -> None:
    for task in list(replace_runner()._tasks):
        await asyncio.wait_for(task, timeout=10)


async def test_replacing_needs_the_name_and_a_clean_check(  # type: ignore[no-untyped-def]
    real_db: RealDb,
    make_real_client: MakeRealClient,
    archive: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeReplace()
    monkeypatch.setattr(replace_runner(), "_run", fake)
    owner = await make_real_client()
    me = await login(owner, real_db.owner_email)
    name = me["org"]["name"]
    path = f"/api/backups/archives/{archive.name}/replace"
    assert (await owner.get("/api/backups/restore")).json() == {"attempt": None}

    for wrong in ("real org", name + " ", "Real"):
        refused = await owner.post(path, json={"confirm": wrong})
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "backup.confirm_mismatch"
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(OTHER_KEY))
    blocked = await owner.post(path, json={"confirm": name})
    assert blocked.status_code == 409
    assert blocked.json()["error"] == {
        **blocked.json()["error"],
        "code": "backup.replace_refused",
        "details": {"problems": ["restore.secret_key_mismatch"]},
    }
    assert fake.calls == [] and await _audit(real_db, "backup.restore_requested") == []

    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(KEY))
    started = await owner.post(path, json={"confirm": name})
    assert started.status_code == 202, started.text
    assert started.json() == {"archive_name": archive.name}
    await _settled()
    (call,) = fake.calls
    assert (call["archive"], call["confirm"], call["via"]) == (archive, name, "admin")
    assert (call["without_secrets"], call["wait"]) == (False, False)
    (requested,) = await _audit(real_db, "backup.restore_requested")
    assert requested.actor_type == "user" and requested.details == {"archive": archive.name}
    status = (await owner.get("/api/backups/restore")).json()["attempt"]
    assert (status["state"], status["archive_name"], status["code"]) == (
        "requested",
        archive.name,
        None,
    )

    refusing = FakeReplace(refuse=["restore.safety_backup_failed:backup.dump_failed"])
    monkeypatch.setattr(replace_runner(), "_run", refusing)
    assert (await owner.post(path, json={"confirm": name})).status_code == 202
    await _settled()
    (failed,) = await _audit(real_db, "backup.restore_failed")
    assert failed.actor_type == "system"
    assert failed.details == {
        "archive": archive.name,
        "code": "restore.safety_backup_failed:backup.dump_failed",
        "via": "admin",
    }
    status = (await owner.get("/api/backups/restore")).json()["attempt"]
    assert (status["state"], status["code"]) == (
        "failed",
        "restore.safety_backup_failed:backup.dump_failed",
    )


async def test_one_replace_at_a_time(  # type: ignore[no-untyped-def]
    real_db: RealDb,
    make_real_client: MakeRealClient,
    archive: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()

    async def slow(settings: Any, archive: Path, **kwargs: Any) -> None:
        await release.wait()

    monkeypatch.setattr(replace_runner(), "_run", slow)
    owner = await make_real_client()
    me = await login(owner, real_db.owner_email)
    path = f"/api/backups/archives/{archive.name}/replace"
    assert (await owner.post(path, json={"confirm": me["org"]["name"]})).status_code == 202
    again = await owner.post(path, json={"confirm": me["org"]["name"]})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "backup.restore_running")
    release.set()
    await _settled()


async def test_a_restore_after_the_request_clears_the_requested_state(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    """Review M9b F8: a safety archive holds its replace's `backup.restore_requested`
    as the newest attempt; restoring it brings that along, and `backup.restored`
    (newer) ends it: the page shows no stale "angefordert"."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    for action in ("backup.restore_requested", "backup.restored"):
        async with real_db.database.session_factory() as session:
            await record_system(
                session, real_db.org_id, action, "organization", real_db.org_id,
                {"archive": "herd-x.tar"},
            )  # fmt: skip
            await session.commit()
        status = (await owner.get("/api/backups/restore")).json()["attempt"]
        if action == "backup.restore_requested":
            assert status["state"] == "requested"
    assert status is None
