"""Restore checks (plan M9 decisions 5 and 6, review focus 1): an archive that does not
fit is refused with a code, and the target is left exactly as it was."""

import tarfile
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.core.db import make_engine
from app.ops.restore import RestoreRefused, restore_into_empty
from app.ops.restore_checks import check_restore
from tests.factories import login
from tests.factories_restore import (
    AT,
    OTHER_KEY,
    Target,
    add_encrypted_connection,
    make_archive,
    reseal,
    rewrite_manifest,
    source_settings,
)
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.test_wiki_attachment_commit import PDF, PNG, _page_with

Spoil = Callable[[Path, Target], Awaitable[None]]


async def _newer(archive: Path, target: Target) -> None:
    rewrite_manifest(archive, alembic_revision="ffffffffffff")


async def _not_empty(archive: Path, target: Target) -> None:
    engine = make_engine(target.settings.database())
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE stray (x int)"))
    await engine.dispose()


async def _file_conflict(archive: Path, target: Target) -> None:
    _stray_file(archive, target)


def _stray_file(archive: Path, target: Target) -> None:
    with tarfile.open(archive) as tar:
        key = next(n for n in tar.getnames() if n.startswith("herd/files/"))
    path = target.settings.data_dir / key.removeprefix("herd/files/")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"other bytes under the same key")


async def _server_too_old(archive: Path, target: Target) -> None:
    rewrite_manifest(archive, server_major=99)


async def _tools_too_old(archive: Path, target: Target) -> None:
    rewrite_manifest(archive, pg_dump_version="99.1")


async def _key_mismatch(archive: Path, target: Target) -> None:
    target.settings = target.settings.model_copy(update={"secret_key": SecretStr(OTHER_KEY)})


async def _key_missing(archive: Path, target: Target) -> None:
    target.settings = target.settings.model_copy(update={"secret_key": None})


async def _changed_member(archive: Path, target: Target) -> None:
    _flip_in_pdf(archive)


async def _truncated(archive: Path, target: Target) -> None:
    _cut_in_pdf(archive)


def _flip_in_pdf(archive: Path) -> None:
    data = bytearray(archive.read_bytes())
    data[data.index(PDF) + 3] ^= 0xFF
    archive.write_bytes(bytes(data))
    reseal(archive)


def _cut_in_pdf(archive: Path) -> None:
    data = archive.read_bytes()
    archive.write_bytes(data[: data.index(PDF) + 5])
    reseal(archive)


SPOILS: dict[str, Spoil] = {
    "restore.archive_newer": _newer,
    "restore.target_not_empty": _not_empty,
    "restore.file_conflict": _file_conflict,
    "restore.server_too_old": _server_too_old,
    "restore.tools_too_old": _tools_too_old,
    "restore.secret_key_mismatch": _key_mismatch,
    "restore.secret_key_missing": _key_missing,
    "archive.member_checksum": _changed_member,
    "archive.truncated": _truncated,
}


@pytest.mark.parametrize("code", sorted(SPOILS))
async def test_a_refused_restore_leaves_the_target_untouched(
    code: str,
    real_db: RealDb,
    make_real_client: MakeRealClient,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF))
    await add_encrypted_connection(real_db, monkeypatch)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await SPOILS[code](archive, target)
    tables, files = await target.tables(), target.files()

    check = await check_restore(target.settings, archive)
    assert code in check.problems
    with pytest.raises(RestoreRefused) as refused:
        await restore_into_empty(
            target.settings, archive, without_secrets=False, clock=SettableClock(AT)
        )
    assert code in refused.value.problems
    assert await target.tables() == tables
    assert target.files() == files


async def test_a_good_archive_checks_clean_and_names_missing_env_references(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_encrypted_connection(real_db, monkeypatch)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    rewrite_manifest(archive, env_refs=["HERD_AI_GONE", "HERD_AI_THERE"])
    monkeypatch.setenv("HERD_AI_THERE", "x")
    monkeypatch.delenv("HERD_AI_GONE", raising=False)
    check = await check_restore(target.settings, archive)
    assert check.problems == []
    assert check.warnings == ["restore.env_missing:HERD_AI_GONE"]
    assert check.manifest is not None and check.manifest.env_refs == [
        "HERD_AI_GONE",
        "HERD_AI_THERE",
    ]


async def test_a_wrong_key_lists_the_unreadable_columns(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_encrypted_connection(real_db, monkeypatch)
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await _key_mismatch(archive, target)
    check = await check_restore(target.settings, archive)
    assert check.problems == ["restore.secret_key_mismatch"]
    assert check.warnings == ["restore.secrets_unreadable:ai_connection.secret_ref=1"]
    # The previous key of the target may be the archive's.
    target.settings = target.settings.model_copy(
        update={"secret_key_previous": SecretStr("r" * 40)}
    )
    assert (await check_restore(target.settings, archive)).problems == []
