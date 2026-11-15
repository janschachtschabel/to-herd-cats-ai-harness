"""Restoring an archive into an empty installation (plan M9 task 2, decisions 5 and 6):
every row and file comes back, an older revision is migrated to head, sessions are
gone, running backups become interrupted, a foreign key leaves the secrets unreadable
but the rest restored, and a restore and a migration never run at once."""

import asyncio
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.core import secrets
from app.core.config import get_settings
from app.core.db import Database, make_engine, set_database
from app.core.listen import asyncpg_dsn
from app.core.migrations import alembic_config, upgrade_head
from app.models_registry import Base
from app.modules.ai.models import AiConnection
from app.modules.audit.models import AuditLog
from app.modules.backups.models import BackupRun
from app.ops.archive import read_sidecar
from app.ops.backup import write_archive
from app.ops.cli import run
from app.ops.restore import restore_into_empty
from app.ops.restore_after import CLEARED_AFTER_RESTORE
from app.ops.schema_lock import schema_lock
from app.web.public import create_public_app
from scripts.compare_databases import compare
from tests.factories import CSRF, login
from tests.factories_restore import (
    AT,
    OTHER_KEY,
    Target,
    add_encrypted_connection,
    make_archive,
    source_settings,
)
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.test_wiki_attachment_commit import PDF, PNG, _page_with


async def _target_client(target: Target) -> tuple[AsyncClient, Database]:
    database = Database(target.settings.database())
    set_database(database)
    client = AsyncClient(
        transport=ASGITransport(app=create_public_app(), raise_app_exceptions=False),
        base_url="http://test",
        headers=CSRF,
    )
    return client, database


async def test_restore_into_an_empty_database_brings_every_row_and_file_back(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, attachments = await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF))
    archive = await make_archive(source_settings(tmp_path, data_dir))
    manifest, _ = read_sidecar(archive)

    report = await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    assert report.revision_from == report.revision_to == manifest.alembic_revision
    assert report.files == 2
    tables = await target.tables()
    expected = dict(manifest.tables)
    for name in CLEARED_AFTER_RESTORE:
        expected[name] = 0
    expected["audit_log"] += 1  # `backup.restored`
    assert tables == expected == report.tables
    assert expected["user_session"] == 0 and manifest.tables["user_session"] >= 1
    files = target.files()
    assert {k.rsplit("/", 1)[1] for k in files} == {a["sha256"] for a in attachments}
    assert all(k.rsplit("/", 1)[1] == sha for k, sha in files.items())


async def test_sessions_are_gone_after_restore_and_login_works(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    client, database = await _target_client(target)
    try:
        client.cookies.update(owner.cookies)  # the session of the source
        assert (await client.get("/api/auth/me")).status_code == 401
        client.cookies.clear()
        await login(client, real_db.owner_email)
        assert (await client.get("/api/auth/me")).status_code == 200
    finally:
        await client.aclose()
        set_database(real_db.database)
        await database.dispose()


async def test_running_backup_rows_become_interrupted(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    engine = make_engine(target.settings.database())
    try:
        async with engine.connect() as conn:
            states = (await conn.scalars(select(BackupRun.state))).all()
            entry = (
                await conn.execute(select(AuditLog).where(AuditLog.action == "backup.restored"))
            ).one()
    finally:
        await engine.dispose()
    assert states == ["interrupted"]  # the archive's own run was running in its snapshot
    assert entry.actor_type == "system"
    assert entry.details == {
        "archive": archive.name,
        "revision_from": entry.details["revision_to"],
        "revision_to": entry.details["revision_to"],
    }


async def test_an_older_archive_is_migrated_to_head(
    target: Target, tmp_path: Path, data_dir: Path
) -> None:
    script = ScriptDirectory.from_config(alembic_config())
    (head,) = script.get_heads()
    older = script.get_revision(head).down_revision
    assert isinstance(older, str)
    # A source of its own at the revision before head, with an organisation.
    source = Target(target.settings.model_copy(), "older")
    async with _scratch(target, "older") as url:
        source.settings = source_settings(tmp_path, data_dir).model_copy(
            update={"database_url": url}
        )
        engine = make_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: _upgrade_to(c, older))
            await conn.execute(
                text("INSERT INTO organization (id, name) VALUES (gen_random_uuid(), 'Alt')")
            )
        await engine.dispose()
        archive = tmp_path / "older.tar"
        await write_archive(source.settings, archive, AT)
    report = await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    assert (report.revision_from, report.revision_to) == (older, head)
    assert report.tables["organization"] == 1


async def test_without_secrets_restores_and_connections_report_secret_unavailable(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_encrypted_connection(real_db, monkeypatch)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    target.settings = target.settings.model_copy(update={"secret_key": SecretStr(OTHER_KEY)})
    report = await restore_into_empty(
        target.settings, archive, without_secrets=True, clock=SettableClock(AT)
    )
    assert report.tables["ai_connection"] == 1
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(OTHER_KEY))
    engine = make_engine(target.settings.database())
    try:
        async with engine.connect() as conn:
            ref = await conn.scalar(select(AiConnection.secret_ref))
    finally:
        await engine.dispose()
    assert ref is not None and ref.startswith("enc:")
    with pytest.raises(secrets.SecretUnavailable):
        secrets.resolve(ref)


async def test_restore_and_migrate_exclude_each_other(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    holder = make_engine(target.settings.database())
    try:
        async with holder.connect() as conn, schema_lock(conn):
            restoring = asyncio.create_task(
                restore_into_empty(
                    target.settings, archive, without_secrets=False, clock=SettableClock(AT)
                )
            )
            await _waiting_for_the_lock(target)
            assert not restoring.done() and await target.tables() == {}
        await restoring
        # The other way round: a migration waits for a restore's lock.
        async with holder.connect() as conn, schema_lock(conn):
            migrating = asyncio.create_task(_migrate(target))
            await _waiting_for_the_lock(target)
            assert not migrating.done()
        await migrating
    finally:
        await holder.dispose()


async def _migrate(target: Target) -> None:
    engine = make_engine(target.settings.database())
    try:
        async with engine.begin() as conn:
            await conn.run_sync(upgrade_head)
    finally:
        await engine.dispose()


async def _waiting_for_the_lock(target: Target) -> None:
    engine = make_engine(target.settings.database())
    try:
        for _ in range(500):
            async with engine.connect() as conn:
                waiting = await conn.scalar(
                    text(
                        "SELECT count(*) FROM pg_locks l JOIN pg_database d ON d.oid = l.database"
                        " WHERE l.locktype = 'advisory' AND NOT l.granted AND d.datname = :name"
                    ),
                    {"name": target.name},
                )
            if waiting:
                return
            await asyncio.sleep(0.02)
        raise AssertionError("nobody waits for the schema lock")
    finally:
        await engine.dispose()


def _upgrade_to(connection: Connection, revision: str) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


class _scratch:  # noqa: N801
    """A second scratch database next to the target's."""

    def __init__(self, target: Target, suffix: str) -> None:
        self.url = target.settings.database().set(database=f"{target.name}_{suffix}")
        self.admin = target.settings.database()

    async def __aenter__(self) -> str:
        self.conn = await asyncpg.connect(asyncpg_dsn(self.admin))
        await self.conn.execute(f'CREATE DATABASE "{self.url.database}"')
        return self.url.render_as_string(hide_password=False)

    async def __aexit__(self, *exc: object) -> None:
        await self.conn.execute(f'DROP DATABASE IF EXISTS "{self.url.database}" WITH (FORCE)')
        await self.conn.close()


def test_every_table_cleared_after_a_restore_exists() -> None:
    assert set(CLEARED_AFTER_RESTORE) <= set(Base.metadata.tables)


async def test_restore_from_the_command_line(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    clock = SettableClock(AT)
    assert await run(["restore", "check", str(archive)], target.settings, clock) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "ok"
    assert await run(["restore", "apply", str(archive)], target.settings, clock) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith(f"restored {archive.name}: revision ")
    # Now the target is not empty: refused, with the code.
    assert await run(["restore", "check", str(archive)], target.settings, clock) == 1
    assert capsys.readouterr().out.split()[-1] == "restore.target_not_empty"
    assert await run(["restore", "apply", str(archive)], target.settings, clock) == 1
    assert capsys.readouterr().out.split()[-1] == "restore.target_not_empty"


async def test_compare_databases_finds_no_difference_after_a_restore(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    await _page_with(owner, ("a.png", PNG))
    source = source_settings(tmp_path, data_dir)
    archive = await make_archive(source)
    await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    ignore = {*CLEARED_AFTER_RESTORE, "audit_log", "backup_run"}
    assert await compare(source.database(), target.settings.database(), ignore) == []
    # A changed row is found (by its table's checksum), and named by table only.
    engine = make_engine(target.settings.database())
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE page SET title = title || ' (geändert)'"))
    await engine.dispose()
    assert await compare(source.database(), target.settings.database(), ignore) == [
        "page: rows equal, content differs"
    ]
