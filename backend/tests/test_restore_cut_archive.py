"""An archive that changes between the checks and the apply (module review M9a
re-check): a dump member cut off midway ends the restore as `failed <code>`, like any
other failed restore, with the database left empty and the files it added removed."""

import tarfile
from pathlib import Path

import pytest

from app.ops import restore as restore_module
from app.ops.archive import DUMP_MEMBER, PREFIX
from app.ops.cli import run
from app.ops.manifest import Manifest
from tests.factories import login
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.test_wiki_attachment_commit import PNG, _page_with


def _cut_the_dump(archive: Path) -> None:
    with tarfile.open(archive, "r:") as tar:
        info = tar.getmember(PREFIX + DUMP_MEMBER)
    with archive.open("r+b") as raw:
        raw.truncate(info.offset_data + info.size // 2)


async def test_a_dump_member_cut_off_after_the_checks_fails_with_a_code(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    await _page_with(owner, ("a.png", PNG))
    archive = await make_archive(source_settings(tmp_path, data_dir))
    restore_files = restore_module.restore_files

    async def restore_files_then_cut(storage: object, path: Path, manifest: Manifest) -> list[str]:
        added = await restore_files(storage, path, manifest)  # type: ignore[arg-type]
        assert added  # the attachment was written
        _cut_the_dump(path)  # the file changes on disk after it was checked
        return added

    monkeypatch.setattr(restore_module, "restore_files", restore_files_then_cut)
    code = await run(["restore", "apply", str(archive)], target.settings, SettableClock(AT))

    assert code == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "failed archive.truncated"
    assert await target.tables() == {}
    assert target.files() == {}
