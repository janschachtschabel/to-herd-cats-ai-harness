"""Hostile ZIP files cost no memory (review M2 R5): what an archive declares about
itself (entry count, directory size) is never trusted; the central directory is
walked with bounded memory and the walk stops at the limit."""

import io
import struct
import tracemalloc
import zipfile
from collections.abc import Callable

import pytest

from app.modules.wiki import archive, filetypes
from app.modules.wiki.archive import ArchiveTooLarge

_LOCAL = b"PK\x03\x04" + bytes(26)  # starts like a ZIP, so type detection opens it
FLAT = 8 * 1024 * 1024  # bytes of Python allocations a hostile archive may cost


def _lying_zip(entries: int, declared: int = 1) -> bytes:
    """A central directory of `entries` minimal records whose end record states
    `declared` entries (no file data: the directory alone is the attack)."""
    directory = bytearray()
    for i in range(entries):
        name = b"%07d.md" % i
        directory += struct.pack(
            "<4s4B4HL2L5H2L", b"PK\x01\x02", 20, 0, 20, 0, 0, 0, 0, 0, 0, 0, 0, len(name),
            0, 0, 0, 0, 0, 0,
        ) + name  # fmt: skip
    end = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, declared, declared, len(directory), 0, 0)
    return _LOCAL + bytes(directory) + end


def _peak(work: Callable[[], object]) -> int:
    tracemalloc.start()
    try:
        work()
    except Exception:  # noqa: BLE001 - refused or not, only the memory matters here
        pass
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def _honest_zip(entries: int, prefix: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as written:
        if prefix:
            written.writestr("[Content_Types].xml", "<Types/>")
        for i in range(entries):
            written.writestr(f"{prefix}{i}.txt", "x")
    return buffer.getvalue()


def test_a_directory_with_more_entries_than_declared_is_refused_with_flat_memory() -> None:
    data = _lying_zip(200_000)  # about 10 MB of directory, the end record says 1
    with pytest.raises(ArchiveTooLarge):
        archive.open_archive(io.BytesIO(data))
    assert _peak(lambda: archive.open_archive(io.BytesIO(data))) < FLAT


def test_a_declared_count_that_disagrees_with_the_directory_is_invalid() -> None:
    data = _lying_zip(3, declared=5)
    with pytest.raises(Exception) as refused:
        archive.open_archive(io.BytesIO(data))
    assert getattr(refused.value, "code", None) == "import.invalid_zip"


def test_an_oversized_directory_is_refused_before_it_is_read() -> None:
    # Within the entry limit, but each record carries a 60 KB comment (4.8 MB).
    big = bytearray()
    for i in range(80):
        name = b"%03d.md" % i
        big += struct.pack(
            "<4s4B4HL2L5H2L", b"PK\x01\x02", 20, 0, 20, 0, 0, 0, 0, 0, 0, 0, 0, len(name),
            0, 60_000, 0, 0, 0, 0,
        ) + name + b"c" * 60_000  # fmt: skip
    end = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 80, 80, len(big), 0, 0)
    with pytest.raises(ArchiveTooLarge):
        archive.open_archive(io.BytesIO(_LOCAL + bytes(big) + end))


def test_honest_archives_still_open() -> None:
    with archive.open_archive(io.BytesIO(_honest_zip(2000))) as opened:
        assert len(opened.infolist()) == 2000
    with pytest.raises(ArchiveTooLarge):
        archive.open_archive(io.BytesIO(_honest_zip(2001)))


def test_type_detection_of_a_hostile_zip_costs_no_memory() -> None:
    data = _lying_zip(200_000)
    peak = _peak(lambda: filetypes.detect(data[:4096], False, io.BytesIO(data), "x.zip"))
    assert peak < FLAT


def test_type_detection_still_knows_large_zips_and_office_files() -> None:
    big = _honest_zip(5000)
    assert filetypes.detect(big[:4096], False, io.BytesIO(big), "x.zip") is filetypes.ZIP
    docx = _honest_zip(3, prefix="word/")
    assert filetypes.detect(docx[:4096], False, io.BytesIO(docx), "a.docx") is filetypes.DOCX
    broken = _lying_zip(3, declared=5)
    with pytest.raises(filetypes.UnsupportedType):
        filetypes.detect(broken[:4096], False, io.BytesIO(broken), "x.zip")
