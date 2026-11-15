"""Backups from the command line (plan M9 task 1, decisions 2 to 5 and 11): one
snapshot gives the dump, the row counts and the attachment files; the run is recorded
in `backup_run`; pg_dump gets the password only in its environment."""

import hashlib
import os
import re
import stat
import subprocess
import tarfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.config import Settings, get_settings
from app.core.migrations import alembic_config
from app.modules.ai.models import AiConnection
from app.modules.audit.models import AuditLog
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.orgs.models import Organization
from app.ops import backup as backup_module
from app.ops.archive import read_sidecar, verify_archive
from app.ops.backup import create_backup
from app.ops.snapshot import secret_figures
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.test_wiki_attachment_commit import PDF, PNG, _page_with

AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)
KEY = "b" * 40


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "backups",
        data_dir=data_dir,
        secret_key=SecretStr(KEY),
    )


def _fake_tool(tmp_path: Path, name: str, body: str) -> Path:
    """A `name` on a directory put first on PATH; `--version` answers like the real one."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    real = subprocess.run([name, "--version"], capture_output=True, text=True, check=True)
    script = bin_dir / name
    script.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "{real.stdout.strip()}"; exit 0; fi\n' + body
    )
    script.chmod(0o755)
    return bin_dir


def _read_seen(seen: Path) -> tuple[list[str], dict[str, str]]:
    argv = Path(f"{seen}.argv").read_text().splitlines()
    lines = Path(f"{seen}.env").read_text().splitlines()
    return argv, dict(line.split("=", 1) for line in lines if "=" in line)


async def _runs(real_db: RealDb) -> list[BackupRun]:
    async with real_db.database.session_factory() as s:
        return list((await s.scalars(select(BackupRun).order_by(BackupRun.started_at))).all())


async def _counts(real_db: RealDb) -> dict[str, int]:
    async with real_db.database.session_factory() as s:
        names = (
            await s.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
            )
        ).all()
        return {n: int(await s.scalar(text(f'SELECT count(*) FROM "{n}"')) or 0) for n in names}


def _dumped_attachment_keys(archive: Path, tmp_path: Path) -> set[str]:
    """The `storage_key` of every attachment row in the archive's dump."""
    with tarfile.open(archive) as tar:
        member = tar.extractfile("herd/db.dump")
        assert member is not None
        (tmp_path / "db.dump").write_bytes(member.read())
    sql = subprocess.run(
        ["pg_restore", "-f", "-", "--data-only", "-t", "attachment", str(tmp_path / "db.dump")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    copy = re.search(
        r"^COPY public\.attachment \(([^)]*)\) FROM stdin;\n(.*?)^\\\.$", sql, re.M | re.S
    )
    assert copy is not None
    column = [c.strip() for c in copy.group(1).split(",")].index("storage_key")
    return {line.split("\t")[column] for line in copy.group(2).splitlines() if line}


def _archived_files(archive: Path) -> dict[str, bytes]:
    with tarfile.open(archive) as tar:
        found = {}
        for info in tar.getmembers():
            if info.name.startswith("herd/files/"):
                handle = tar.extractfile(info)
                assert handle is not None
                found[info.name.removeprefix("herd/files/")] = handle.read()
        return found


async def test_create_backup_writes_dump_files_and_manifest(
    real_db: RealDb, make_real_client: MakeRealClient, settings: Settings, tmp_path: Path
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, attachments = await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF), ("c.png", PNG))
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SettableClock(AT))

    assert outcome.state == BackupState.OK and outcome.error_code is None
    archive = outcome.archive
    assert archive is not None and archive.parent == settings.backup_dir
    assert archive.name == "herd-20261115T023007Z-0.1.0.tar"
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert verify_archive(archive) == []
    manifest, archive_sha256 = read_sidecar(archive)
    (head,) = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert manifest.alembic_revision == head
    assert manifest.created_at == "2026-11-15T02:30:07Z"
    counts = await _counts(real_db)
    counts["audit_log"] -= 1  # `backup.created`, written after the snapshot
    assert manifest.tables == counts and counts["backup_run"] == 1  # its own, running
    assert manifest.server_major >= 16
    assert manifest.key_id == secrets.key_id(KEY)
    assert manifest.storage == "local"
    files = _archived_files(archive)
    assert len(files) == 2  # one file per content
    for key, data in files.items():
        assert key.startswith(f"attachments/{real_db.org_id}/")
        assert hashlib.sha256(data).hexdigest() == key.rsplit("/", 1)[1]
    assert manifest.files == {"count": 2, "bytes": len(PNG) + len(PDF)}
    assert {a["sha256"] for a in attachments} == {k.rsplit("/", 1)[1] for k in files}

    (run,) = await _runs(real_db)
    assert run.id == outcome.run_id and run.org_id == real_db.org_id
    assert (run.trigger, run.state, run.error_code) == ("cli", "ok", None)
    assert run.archive == archive.name and run.bytes == archive.stat().st_size
    assert run.archive_sha256 == archive_sha256
    assert run.started_at == AT and run.finished_at == AT
    async with real_db.database.session_factory() as s:
        entry = await s.scalar(select(AuditLog).where(AuditLog.action == "backup.created"))
    assert entry is not None and entry.actor_type == "system"
    assert entry.target_id == run.id
    assert entry.details == {"archive": archive.name, "bytes": run.bytes, "via": "cli"}


async def test_a_backup_during_uploads_and_deletes_is_self_consistent(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    page, (png, pdf) = await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF))
    real_dump: Callable[..., Any] = backup_module.dump

    async def dump_while_writing(*args: Any, **kwargs: Any) -> None:
        # The snapshot is taken: now one attachment goes and another comes, committed.
        assert (await owner.delete(pdf["url"])).status_code == 204
        r = await owner.post(
            f"/api/pages/{page['id']}/attachments",
            params={"filename": "new.txt"},
            content=b"brand new text",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert r.status_code == 201, r.text
        await real_dump(*args, **kwargs)

    monkeypatch.setattr(backup_module, "dump", dump_while_writing)
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SettableClock(AT))

    assert outcome.state == BackupState.OK and outcome.archive is not None
    files = _archived_files(outcome.archive)
    assert set(files) == _dumped_attachment_keys(outcome.archive, tmp_path)
    assert {k.rsplit("/", 1)[1] for k in files} == {png["sha256"], pdf["sha256"]}
    manifest, _ = read_sidecar(outcome.archive)
    assert manifest.tables["attachment"] == 2
    assert verify_archive(outcome.archive) == []


async def test_no_password_in_argv(
    real_db: RealDb,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = tmp_path / "seen"
    bin_dir = _fake_tool(
        tmp_path,
        "pg_dump",
        f'printf "%s\\n" "$@" > {seen}.argv\nenv > {seen}.env\nexec /usr/bin/pg_dump "$@"\n',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("HERD_SECRET_KEY", KEY)
    monkeypatch.setenv("HERD_DATABASE_PASSWORD", "from-the-app-env")
    url = settings.database()
    password = url.password
    assert password
    split = settings.model_copy(
        update={"database_url": url.set(password=None).render_as_string(hide_password=False)}
    )
    split._database_password = SecretStr(str(password))
    outcome = await create_backup(split, trigger=BackupTrigger.CLI, clock=SettableClock(AT))
    assert outcome.state == BackupState.OK, outcome.error_code
    argv, env = _read_seen(seen)
    # The URL's user and password equal here ("herd"): no URL, no value of its own.
    assert argv and not any(
        "://" in a or "@" in a or a == password or a.endswith(f"={password}") for a in argv
    )
    assert env["PGPASSWORD"] == password
    assert not any(name.startswith("HERD_") for name in env)


async def test_failed_dump_marks_the_run_failed_and_leaves_no_archive(
    real_db: RealDb,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = _fake_tool(tmp_path, "pg_dump", "echo 'pg_dump: error: boom' >&2\nexit 1\n")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SettableClock(AT))
    assert (outcome.state, outcome.archive) == (BackupState.FAILED, None)
    assert outcome.error_code == "backup.dump_failed"
    assert list(settings.backup_dir.iterdir()) == []
    (run,) = await _runs(real_db)
    assert (run.state, run.error_code, run.archive, run.bytes) == (
        "failed",
        "backup.dump_failed",
        None,
        None,
    )
    assert run.finished_at == AT


async def test_secret_figures_count_enc_values_and_name_env_references(
    session: AsyncSession, org: Organization, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(KEY))
    for name, ref in (
        ("A", secrets.encrypt("sk-one")),
        ("B", secrets.encrypt("sk-two")),
        ("C", "env:HERD_AI_OPENAI"),
        ("D", "env:HERD_AI_OPENAI"),
        ("E", "env:HERD_AI_LOCAL"),
    ):
        session.add(
            AiConnection(
                org_id=org.id,
                name=name,
                kind="openai",
                base_url="https://api.openai.com/v1",
                secret_ref=ref,
                models=[],
                param_family="max_tokens",
                extra_body={},
                data_location="external",
                purpose="chat",
            )
        )
    await session.flush()
    connection = await session.connection()
    enc_values, env_refs = await secret_figures(connection)
    assert enc_values["ai_connection.secret_ref"] == 2
    assert enc_values["connector.refresh_token_ref"] == 0
    assert set(enc_values) >= {"oauth_client.client_secret_ref", "oauth_flow.verifier_ref"}
    assert env_refs == ["HERD_AI_LOCAL", "HERD_AI_OPENAI"]
    assert await session.scalar(select(func.count()).select_from(AiConnection)) == 5
