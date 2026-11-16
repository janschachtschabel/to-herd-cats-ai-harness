"""Moving attachments between the local directory and S3 (plan M9 task 14):
`python -m app.ops storage copy --to s3|local` copies what the target lacks (or holds
with another size), again and again without harm, and `storage check` writes, reads
and removes a probe."""

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.storage import LocalStorage
from app.ops.cli import run
from tests.factories_s3 import s3_settings_for
from tests.support.clock import SettableClock
from tests.support.s3_stub import S3Stub, StoredObject

FILES = {f"attachments/org/{c * 8}": c.encode() * (i + 1) for i, c in enumerate("abc")}


async def _one(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _local(root: Path) -> LocalStorage:
    storage = LocalStorage(root)
    for key, data in FILES.items():
        await storage.put(key, _one(data), size=len(data), sha256=hashlib.sha256(data).hexdigest())
    (root / "attachments" / "org" / ".aaaaaaaa.1.part").write_bytes(b"left over")
    (root / "tmp").mkdir()
    (root / "tmp" / "tmpabc123").write_bytes(b"a spool")
    return storage


def _settings(stub: S3Stub, tmp_path: Path, storage: str = "local") -> Settings:
    return s3_settings_for(
        stub, base=Settings(data_dir=tmp_path / "data"), storage=storage, s3_prefix="herd"
    )


async def _cli(
    capsys: pytest.CaptureFixture[str], settings: Settings, *argv: str
) -> tuple[int, str]:
    status = await run(argv, settings, SettableClock(datetime(2026, 11, 16, tzinfo=UTC)))
    lines = capsys.readouterr().out.splitlines(keepends=True)
    return status, "".join(line for line in lines if not line.startswith("{"))  # no log lines


async def test_storage_copy_is_idempotent(
    s3_stub: S3Stub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    await _local(tmp_path / "data")
    settings = _settings(s3_stub, tmp_path)
    status, out = await _cli(capsys, settings, "storage", "copy", "--to", "s3")
    assert (status, out.strip()) == (0, "copied 3, present 0, gone 0, 6 bytes")
    assert {k: o.data for k, o in s3_stub.state.objects.items()} == {
        f"herd/{k}": v for k, v in FILES.items()
    }
    puts = sum(1 for e in s3_stub.state.log if e.method == "PUT")

    status, out = await _cli(capsys, settings, "storage", "copy", "--to", "s3")
    assert (status, out.strip()) == (0, "copied 0, present 3, gone 0, 0 bytes")
    assert sum(1 for e in s3_stub.state.log if e.method == "PUT") == puts

    damaged = "herd/attachments/org/bbbbbbbb"
    s3_stub.state.objects[damaged] = StoredObject(b"b", {})
    status, out = await _cli(capsys, settings, "storage", "copy", "--to", "s3")
    assert (status, out.strip()) == (0, "copied 1, present 2, gone 0, 2 bytes")
    assert s3_stub.state.objects[damaged].data == b"bb"


async def test_storage_copy_back_to_local(
    s3_stub: S3Stub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    await _local(tmp_path / "source")
    up = s3_settings_for(s3_stub, base=Settings(data_dir=tmp_path / "source"), s3_prefix="herd")
    assert (await _cli(capsys, up, "storage", "copy", "--to", "s3"))[0] == 0
    down = _settings(s3_stub, tmp_path, storage="s3")
    status, out = await _cli(capsys, down, "storage", "copy", "--to", "local")
    assert (status, out.strip()) == (0, "copied 3, present 0, gone 0, 6 bytes")
    local = LocalStorage(tmp_path / "data")
    assert [k async for k, _ in local.entries("attachments")] == sorted(FILES)


async def test_copy_to_s3_needs_the_s3_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    status, out = await _cli(capsys, settings, "storage", "copy", "--to", "s3")
    assert status == 1
    assert out.startswith("failed storage.s3_settings") and "HERD_S3_ENDPOINT" in out


async def test_copy_reports_an_unreachable_store(
    s3_stub: S3Stub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    await _local(tmp_path / "data")
    settings = _settings(s3_stub, tmp_path)
    s3_stub.state.failures.append(500)
    status, out = await _cli(capsys, settings, "storage", "copy", "--to", "s3")
    assert (status, out.strip()) == (1, "failed s3.failed")


async def test_storage_check(
    s3_stub: S3Stub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    on_s3 = _settings(s3_stub, tmp_path, storage="s3")
    assert await _cli(capsys, on_s3, "storage", "check") == (0, "ok s3\n")
    assert s3_stub.state.objects == {}
    s3_stub.state.failures.append(403)
    assert await _cli(capsys, on_s3, "storage", "check") == (1, "failed s3.denied\n")
    local = Settings(data_dir=tmp_path / "local")
    assert await _cli(capsys, local, "storage", "check") == (0, "ok local\n")
    assert [p for p in (tmp_path / "local").rglob("*") if p.is_file()] == []
