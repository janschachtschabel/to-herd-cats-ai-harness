"""`core/storage.py` (LocalStorage) and `core/uploads.py` (spooling a body)."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.core.storage import LocalStorage, StorageKeyError, StoredFileMissing
from app.core.uploads import PayloadTooLarge, spool


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def _read(storage: LocalStorage, key: str) -> bytes:
    return b"".join([c async for c in await storage.open(key)])


async def test_put_open_delete_round_trip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    assert await storage.put("attachments/org/abc", _stream(b"hello ", b"world")) == 11
    assert await _read(storage, "attachments/org/abc") == b"hello world"
    assert await storage.put("attachments/org/abc", _stream(b"again")) == 5
    assert await _read(storage, "attachments/org/abc") == b"again"
    await storage.delete("attachments/org/abc")
    await storage.delete("attachments/org/abc")  # nothing there is fine
    with pytest.raises(StoredFileMissing):
        await storage.open("attachments/org/abc")
    # No temporary file is left behind.
    assert [p.name for p in (tmp_path / "attachments" / "org").iterdir()] == []


async def test_a_failed_write_leaves_nothing(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    async def broken() -> AsyncIterator[bytes]:
        yield b"part"
        raise RuntimeError("client went away")

    with pytest.raises(RuntimeError):
        await storage.put("a/b", broken())
    assert list((tmp_path / "a").iterdir()) == []


@pytest.mark.parametrize(
    "key",
    [
        "../outside",
        "a/../../outside",
        "/etc/passwd",
        "a//b",
        "a/./b",
        "",
        ".",
        "a/.hidden",
        "A/Upper",
        "a\\b",
        "a/b\x00",
        "a/b/",
    ],
)
async def test_local_storage_rejects_keys_outside_root(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path / "root")
    with pytest.raises(StorageKeyError):
        await storage.put(key, _stream(b"x"))
    with pytest.raises(StorageKeyError):
        await storage.open(key)
    with pytest.raises(StorageKeyError):
        await storage.delete(key)
    assert not (tmp_path / "outside").exists()


async def test_local_storage_does_not_follow_a_symlink_out(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (root / "link").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(StorageKeyError):
        await LocalStorage(root).put("link/file", _stream(b"x"))
    assert list((tmp_path / "elsewhere").iterdir()) == []


async def test_spool_hashes_sizes_and_spills_to_disk() -> None:
    big = b"a" * (3 * 1024 * 1024)
    with await spool(_stream(big[:100], big[100:]), len(big), code="x.too_large") as spooled:
        assert spooled.size == len(big) and spooled.text
        assert spooled.sha256 == __import__("hashlib").sha256(big).hexdigest()
        assert spooled.head == big[:4096]
        assert b"".join([c async for c in spooled.chunks()]) == big


async def test_spool_refuses_more_than_the_limit() -> None:
    with pytest.raises(PayloadTooLarge) as caught:
        await spool(_stream(b"12345", b"6"), 5, code="attachment.too_large")
    assert (caught.value.status_code, caught.value.code) == (413, "attachment.too_large")


@pytest.mark.parametrize(
    ("chunks", "text"),
    [
        ((b"plain text",), True),
        (("Grüße".encode()[:3], "Grüße".encode()[3:]), True),  # a character split in two
        ((b"\xff\xfe",), False),
        ((b"abc\x00def",), False),
        (("ä".encode()[:1],), False),  # cut off at the end
    ],
)
async def test_spool_knows_whether_it_is_text(chunks: tuple[bytes, ...], text: bool) -> None:
    with await spool(_stream(*chunks), 100, code="x") as spooled:
        assert spooled.text is text
