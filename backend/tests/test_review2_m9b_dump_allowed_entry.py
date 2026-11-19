"""Review M9b final, finding F2-1: the fix of F1 judges a dump's entries by kind and
name only. The definition of an allowed entry is still the archive's text, so an
uploaded archive could run a program on the database host through an entry the
allow-list lets pass: what plain `pg_dump` writes for a database someone prepared (a
function under one of the seven allowed names, used by a table's CHECK constraint).
That worked because the shipped stacks gave the application a superuser role.

Ruling: the shipped stacks run the app with a role that owns the database and its
schema and is no superuser; under it the dump's `COPY … TO PROGRAM` cannot run. The
administration refuses to replace as a superuser (409 `restore.superuser_refused`);
the command line only with `--allow-superuser`."""

import asyncio
import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.backups.replacing import replace_runner
from app.ops.cli import run
from app.ops.dump_toc import list_dump
from app.ops.pgtools import ToolFailed, child_env
from app.ops.swap import swap_database
from tests.factories import login
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.factories_roles import database_roles
from tests.real_db import MakeRealClient, RealDb
from tests.replace_helpers import NAME, marked, printed, running, scalar, sql
from tests.support.clock import SettableClock


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _superuser(target: Target) -> bool:
    found = await scalar(
        target.settings, "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    )
    return bool(found)


async def _prepared_dump(target: Target, tmp_path: Path, proof: Path) -> bytes:
    """A plain pg_dump of a database whose function `herd_work_item_hierarchy()` (an
    allowed name) runs a program, called by a CHECK constraint when the data loads."""
    head = "FUNCTION herd_work_item_hierarchy() RETURNS boolean LANGUAGE plpgsql AS "
    await sql(target.settings, f"CREATE {head} $f$ BEGIN RETURN true; END $f$")
    await sql(target.settings, "CREATE TABLE note (a int CHECK (herd_work_item_hierarchy()))")
    await sql(target.settings, "INSERT INTO note VALUES (1)")
    # Only now the body that runs a program: nothing runs while the dump is prepared.
    await sql(
        target.settings,
        f"CREATE OR REPLACE {head} "
        f"$f$ BEGIN COPY (SELECT 1) TO PROGRAM 'touch {proof}'; RETURN true; END $f$",
    )
    out = tmp_path / "prepared.dump"
    process = await asyncio.create_subprocess_exec(
        "pg_dump", "--format=custom", "--no-password", f"--file={out}",
        env=child_env(target.settings),
    )  # fmt: skip
    assert await process.wait() == 0
    await sql(target.settings, "DROP TABLE note")
    await sql(target.settings, "DROP FUNCTION herd_work_item_hierarchy()")
    return out.read_bytes()


async def test_an_allowed_entry_cannot_run_a_program_as_the_owner_role(
    target: Target, tmp_path: Path
) -> None:
    """The dump passes the allow-list, but restored by the role the shipped stacks
    give the app (owner of database and schema, no superuser) the program never runs:
    the swap fails and rolls back."""
    if not await _superuser(target):
        pytest.skip("the proof file is read with pg_stat_file, which needs a superuser")
    proof = Path(tempfile.gettempdir()) / f"herd-review2-m9b-{uuid.uuid4().hex}"
    dump = await _prepared_dump(target, tmp_path, proof)
    try:
        await list_dump(_chunks(dump))  # "Prüfen" judges the dump as ours
        async with database_roles(target) as roles:
            with pytest.raises(ToolFailed) as failed:
                await swap_database(roles.owner_settings(target), _chunks(dump), tail_sql="")
            assert failed.value.code == "restore.swap_failed"
        ran = await scalar(
            target.settings, f"SELECT (pg_stat_file('{proof}', true)).size IS NOT NULL"
        )
        assert not ran, "the uploaded dump ran a shell command as the database server"
    finally:
        await sql(target.settings, f"COPY (SELECT 1) TO PROGRAM 'rm -f {proof}'")


async def test_the_administration_refuses_to_replace_as_a_superuser(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    monkeypatch.setattr(get_settings(), "backup_dir", archive.parent)
    calls: list[Path] = []

    async def never(settings: object, archive: Path, **kwargs: object) -> None:
        calls.append(archive)

    monkeypatch.setattr(replace_runner(), "_run", never)
    owner = await make_real_client()
    me = await login(owner, real_db.owner_email)
    async with real_db.database.session_factory() as session:  # the requests' role
        superuser = await session.scalar(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        )
    if not superuser:
        pytest.skip("the test database's role is no superuser")
    path = f"/api/backups/archives/{archive.name}/replace"
    refused = await owner.post(path, json={"confirm": me["org"]["name"]})
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "restore.superuser_refused"
    assert calls == []
    async with real_db.database.session_factory() as session:
        requested = await session.scalars(
            select(AuditLog).where(AuditLog.action == "backup.restore_requested")
        )
        assert requested.all() == []


async def test_the_command_line_replaces_as_a_superuser_only_when_told(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.ops.replace.DRAIN_SECONDS", 0)
    if not await _superuser(target):
        pytest.skip("the test database's role is no superuser")
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    clock = SettableClock(AT)
    argv = ["restore", "apply", str(archive), "--replace", "--confirm", NAME]
    assert await run(argv, target.settings, clock) == 1
    assert printed(capsys) == "restore.superuser_refused"
    assert await marked(target.settings) == 1  # nothing changed
    assert await run([*argv, "--allow-superuser"], target.settings, clock) == 0
    assert printed(capsys).startswith(f"replaced by {archive.name}: revision ")
    assert await marked(target.settings) == 0


async def test_the_command_line_replaces_as_the_owner_role(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shipped stacks' role (owner, no superuser) restores and replaces without
    the flag."""
    monkeypatch.setattr("app.ops.replace.DRAIN_SECONDS", 0)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    async with database_roles(target) as roles:
        owner = Target(roles.owner_settings(target), target.name)
        await running(owner, archive)
        argv = ["restore", "apply", str(archive), "--replace", "--confirm", NAME]
        assert await run(argv, owner.settings, SettableClock(AT)) == 0, printed(capsys)
        assert printed(capsys).startswith(f"replaced by {archive.name}: revision ")
        assert await marked(owner.settings) == 0
