"""Replacing a running installation whose attachments are in S3 (plan M9 tasks 12 and
14): the archive's files go to the configured store, not to the local directory, and
a replace that fails takes back the objects it wrote."""

import hashlib
from pathlib import Path

import pytest

from app.core.config import Settings
from app.modules.maintenance import repository as maintenance_sql
from app.ops.replace import replace_running
from app.ops.restore import RestoreFailed, restore_into_empty
from tests.factories import login
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.factories_s3 import s3_settings_for
from tests.real_db import MakeRealClient, RealDb
from tests.replace_helpers import MARK, NAME, marked, sql
from tests.support.clock import SettableClock
from tests.support.s3_stub import S3Stub
from tests.test_wiki_attachment_commit import PNG, _page_with

PREFIX = "running"


async def _running_on_s3(stub: S3Stub, target: Target, archive: Path) -> Settings:
    """The target as a running installation on S3 (under PREFIX): restored, then changed."""
    settings = s3_settings_for(stub, base=target.settings, s3_prefix=PREFIX)
    await restore_into_empty(settings, archive, without_secrets=False, clock=SettableClock(AT))
    await sql(
        settings,
        "INSERT INTO user_group (id, org_id, name, version)"
        f" SELECT gen_random_uuid(), id, '{MARK}', 1 FROM organization",
    )
    return settings


def _objects(stub: S3Stub) -> dict[str, str]:
    return {
        k.removeprefix(PREFIX + "/"): hashlib.sha256(o.data).hexdigest()
        for k, o in stub.state.objects.items()
        if k.startswith(PREFIX + "/")
    }


async def _second_archive(
    real_db: RealDb, make_real_client: MakeRealClient, tmp_path: Path, data_dir: Path
) -> tuple[Path, str]:
    """An archive with a file the running installation does not have yet."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, [attachment] = await _page_with(owner, ("b.png", PNG + b"replaced"))
    archive = await make_archive(source_settings(tmp_path / "second", data_dir))
    return archive, f"attachments/{real_db.org_id}/{attachment['sha256']}"


async def test_replace_puts_the_archives_files_into_s3(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_stub: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
) -> None:
    settings = await _running_on_s3(
        s3_stub, target, await make_archive(source_settings(tmp_path, data_dir))
    )
    before = _objects(s3_stub)
    archive, key = await _second_archive(real_db, make_real_client, tmp_path, data_dir)
    assert key not in before
    await replace_running(
        settings,
        archive,
        confirm=NAME,
        without_secrets=False,
        clock=SettableClock(AT),
        drain_seconds=0,
    )
    assert await marked(settings) == 0  # the archive's state
    assert key in _objects(s3_stub)
    assert target.files() == {}  # nothing in the local directory


async def test_a_failed_replace_on_s3_takes_back_the_objects_it_wrote(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    s3_stub: S3Stub,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = await _running_on_s3(
        s3_stub, target, await make_archive(source_settings(tmp_path, data_dir))
    )
    before = _objects(s3_stub)
    archive, _ = await _second_archive(real_db, make_real_client, tmp_path, data_dir)
    stay_on = maintenance_sql.stay_on_sql
    monkeypatch.setattr("app.ops.replace.stay_on_sql", lambda at: stay_on(at) + "SELECT 1 / 0;\n")
    with pytest.raises(RestoreFailed) as failed:
        await replace_running(
            settings,
            archive,
            confirm=NAME,
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=0,
        )
    assert failed.value.code == "restore.swap_failed"
    assert await marked(settings) == 1  # the old state
    assert _objects(s3_stub) == before
    assert target.files() == {}
