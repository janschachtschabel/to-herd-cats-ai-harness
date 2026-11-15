"""Restores in tests (plan M9 task 2): a scratch target database of its own (never
herd_test, dropped afterwards), source archives made from the committed test database
(`real_db`), and changed copies of an archive."""

import dataclasses
import hashlib
import io
import json
import tarfile
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import secrets
from app.core.config import Settings, get_settings
from app.core.db import make_engine
from app.core.listen import asyncpg_dsn
from app.modules.ai.models import AiConnection
from app.modules.backups.models import BackupTrigger
from app.ops.archive import sidecar_of
from app.ops.backup import create_backup
from app.ops.manifest import Manifest
from tests.real_db import RealDb
from tests.support.clock import SettableClock

KEY = "r" * 40
OTHER_KEY = "o" * 40
AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)


@dataclass
class Target:
    settings: Settings
    name: str

    async def tables(self) -> dict[str, int]:
        engine = make_engine(self.settings.database())
        try:
            async with engine.connect() as conn:
                names = (
                    await conn.scalars(
                        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                    )
                ).all()
                return {
                    n: int(await conn.scalar(text(f'SELECT count(*) FROM "{n}"')) or 0)
                    for n in names
                }
        finally:
            await engine.dispose()

    def files(self) -> dict[str, str]:
        root = self.settings.data_dir
        if not root.exists():
            return {}
        return {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }


@pytest.fixture
async def target(tmp_path: Path) -> AsyncIterator[Target]:
    admin = make_url(get_settings().test_database_url)
    name = f"herd_m9a_r_{uuid.uuid4().hex[:10]}"
    connection = await asyncpg.connect(asyncpg_dsn(admin))
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
        settings = Settings(
            database_url=admin.set(database=name).render_as_string(hide_password=False),
            data_dir=tmp_path / "target-data",
            backup_dir=tmp_path / "target-backups",
            secret_key=SecretStr(KEY),
        )
        yield Target(settings, name)
    finally:
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await connection.close()


def source_settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "source-backups",
        data_dir=data_dir,
        secret_key=SecretStr(KEY),
    )


async def add_encrypted_connection(real_db: RealDb, monkeypatch: pytest.MonkeyPatch) -> None:
    """An AI connection whose key is `enc:` under KEY, committed in the source."""
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(KEY))
    async with real_db.database.session_factory() as session:
        session.add(
            AiConnection(
                org_id=real_db.org_id,
                name="Verschlüsselt",
                kind="openai",
                base_url="https://api.openai.com/v1",
                secret_ref=secrets.encrypt("sk-restore-0123456789"),
                models=[],
                param_family="max_tokens",
                extra_body={},
                data_location="external",
                purpose="chat",
            )
        )
        await session.commit()


async def make_archive(settings: Settings) -> Path:
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SettableClock(AT))
    assert outcome.archive is not None, outcome.error_code
    return outcome.archive


def rewrite_manifest(archive: Path, **changes: object) -> None:
    """The archive with its manifest changed (members kept), the sidecar to match."""
    copy = archive.with_name("rewritten.tar")
    with tarfile.open(archive) as tar, tarfile.open(copy, "w", format=tarfile.PAX_FORMAT) as out:
        for info in tar.getmembers():
            handle = tar.extractfile(info)
            assert handle is not None
            data = handle.read()
            if info.name == "herd/manifest.json":
                manifest = dataclasses.replace(Manifest.from_json(data), **changes)  # type: ignore[arg-type]
                data = manifest.to_json()
                info.size = len(data)
            out.addfile(info, io.BytesIO(data))
    copy.replace(archive)
    reseal(archive, **changes)


def reseal(archive: Path, **changes: object) -> None:
    """The sidecar with the archive's new SHA-256 (and `changes`)."""
    sidecar = sidecar_of(archive)
    data = json.loads(sidecar.read_bytes())
    data.update(changes)
    data["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar.write_text(json.dumps(data))
