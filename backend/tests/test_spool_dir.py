"""Temporary files of uploads, imports and exports live under HERD_DATA_DIR/tmp (a
volume, not TMPDIR, which may be RAM); old leftovers are removed at start."""

import os
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import IO

import pytest

from app import launch
from app.core import uploads
from app.core.config import Settings
from app.core.spool import SPOOL_MAX_AGE_SECONDS, remove_stale_spools, spool_dir, spooled_file
from app.core.uploads import MEMORY_BYTES, spool
from app.modules.wiki import export
from tests.factories_wiki import Wiki, new_page


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


def _where(file: IO[bytes]) -> str:
    """The directory the open file was created in (Linux: /proc/self/fd)."""
    rolled = file._file  # type: ignore[attr-defined]
    return os.readlink(f"/proc/self/fd/{rolled.fileno()}")


@pytest.fixture
def elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """TMPDIR points somewhere else, so a file found there would be wrong."""
    other = tmp_path / "other-tmp"
    other.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(other))
    return other


async def test_upload_spool_spills_into_the_data_dir(data_dir: Path, elsewhere: Path) -> None:
    big = b"x" * (MEMORY_BYTES + 10)
    with await spool(_stream(big), len(big), code="x.too_large") as spooled:
        assert spooled.file._rolled  # type: ignore[attr-defined]
        assert _where(spooled.file).startswith(str(data_dir / "tmp") + "/")


def test_spooled_file_creates_the_directory(data_dir: Path, elsewhere: Path) -> None:
    with spooled_file(4) as file:
        file.write(b"12345")
        assert _where(file).startswith(str(spool_dir()) + "/")
    assert spool_dir() == data_dir / "tmp"


def _recording(seen: list[str]) -> Callable[[int], IO[bytes]]:
    """A `spooled_file` that rolls over at once and notes where its file is."""

    def recording(max_size: int) -> IO[bytes]:
        file = spooled_file(max_size)
        file.rollover()  # type: ignore[attr-defined]
        seen.append(_where(file))
        return file

    return recording


async def test_space_export_spools_into_the_data_dir(
    wiki: Wiki, data_dir: Path, elsewhere: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(export, "spooled_file", _recording(seen))
    await new_page(wiki.editor, wiki.space_id, "Seite", content_md="Hallo")
    r = await wiki.editor.get(f"/api/spaces/{wiki.space_id}/export")
    assert r.status_code == 200, r.text
    assert len(seen) == 1 and seen[0].startswith(str(data_dir / "tmp") + "/")


async def test_import_spools_into_the_data_dir(
    wiki: Wiki, data_dir: Path, elsewhere: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(uploads, "spooled_file", _recording(seen))
    r = await wiki.admin.post(
        f"/api/spaces/{wiki.space_id}/import",
        content=b"not a zip",
        headers={"Content-Type": "application/zip"},
    )
    assert r.status_code == 422, r.text
    assert len(seen) == 1 and seen[0].startswith(str(data_dir / "tmp") + "/")


def test_remove_stale_spools_keeps_recent_files(tmp_path: Path) -> None:
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    old, new = tmp / "old", tmp / "new"
    old.write_bytes(b"o")
    new.write_bytes(b"n")
    past = time.time() - SPOOL_MAX_AGE_SECONDS - 60
    os.utime(old, (past, past))
    target = tmp_path / "keep-me"
    target.write_bytes(b"k")
    os.utime(target, (past, past))
    (tmp / "link").symlink_to(target)
    os.utime(tmp / "link", (past, past), follow_symlinks=False)
    assert remove_stale_spools(tmp_path) == 2
    assert sorted(p.name for p in tmp.iterdir()) == ["new"]
    assert target.exists()  # a link is removed, never followed


def test_remove_stale_spools_without_directory_is_fine(tmp_path: Path) -> None:
    assert remove_stale_spools(tmp_path / "missing") == 0


async def test_serve_removes_stale_spools_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[str] = []

    async def fake_bootstrap(settings: Settings) -> None:
        seen.append("bootstrap")

    async def fake_run_servers(servers: object) -> int:
        seen.append("run")
        return 0

    def fake_remove(data_dir: Path) -> int:
        seen.append(f"clean {data_dir}")
        return 0

    monkeypatch.setattr(launch, "bootstrap", fake_bootstrap)
    monkeypatch.setattr(launch, "run_servers", fake_run_servers)
    monkeypatch.setattr(launch, "remove_stale_spools", fake_remove)
    assert await launch.serve(Settings(data_dir=tmp_path)) == 0
    assert seen == [f"clean {tmp_path}", "bootstrap", "run"]
