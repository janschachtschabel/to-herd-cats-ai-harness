"""Reading an uploaded ZIP without trusting it.

- Directory: nothing the archive declares about itself is trusted. The central
  directory is located from the end record and walked record by record with bounded
  memory (`entry_names`); the walk stops at the entry limit, and a directory whose
  records disagree with the declared count or size is no ZIP. Only then does `zipfile`
  parse it, and only up to `MAX_DIRECTORY_BYTES`.
- zip64: an import is at most 100 MiB, so no archive needs it. One that has a zip64
  locator (which `zipfile` would follow to a directory of its own) or an end record
  asking for zip64 is refused before `zipfile` sees it (review M2 S4).
- Size: the sum of the declared sizes is checked up front; reads are bounded too, and
  `zipfile` never yields more than an entry declares (a lie fails its CRC check).
- Names: no absolute paths, drive letters, `..`, symlinks or other special files; the
  caller gets clean segments or a reason to skip the entry.
"""

import io
import stat
import struct
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import IO

from app.core.errors import AppError, ValidationFailed

MAX_ENTRIES = 2000
MAX_UNPACKED_BYTES = 200 * 1024 * 1024
# What 2,000 ordinary records take with room to spare (about 150 bytes each in practice).
MAX_DIRECTORY_BYTES = MAX_ENTRIES * 2048

_EOCD = b"PK\x05\x06"
_EOCD64_LOCATOR = b"PK\x06\x07"
_RECORD = b"PK\x01\x02"
_RECORD_BYTES = 46
_TAIL = 22 + 0xFFFF  # the record plus the longest comment


class ArchiveTooLarge(AppError):
    status_code = 413
    code = "import.too_large"


def invalid_zip() -> ValidationFailed:
    return ValidationFailed(code="import.invalid_zip")


@dataclass(frozen=True, slots=True)
class Directory:
    """Where the central directory is (`start`, `size` in bytes) and how many records
    it claims to hold."""

    start: int
    size: int
    entries: int


def directory(file: IO[bytes]) -> Directory:
    """The central directory as the last end record states it; `invalid_zip` when there
    is none, it points outside the file, or the archive uses zip64."""
    file.seek(0, io.SEEK_END)
    length = file.tell()
    base = max(0, length - _TAIL)
    file.seek(base)
    tail = file.read()
    at = tail.rfind(_EOCD)
    if at < 0 or len(tail) - at < 22:
        raise invalid_zip()
    entries, size, _ = struct.unpack("<HLL", tail[at + 10 : at + 20])
    end = base + at
    # `zipfile` looks for a zip64 locator right before the end record, whatever the end
    # record says; read it there too, in case the tail does not reach back so far.
    file.seek(max(0, end - 20))
    if entries == 0xFFFF or size == 0xFFFFFFFF or file.read(4) == _EOCD64_LOCATOR:
        raise invalid_zip()
    if size > end:
        raise invalid_zip()
    return Directory(start=end - size, size=size, entries=int(entries))


def entry_names(file: IO[bytes], found: Directory, limit: int | None) -> Iterator[bytes]:
    """The raw name of each record of the central directory, read one record at a
    time (memory stays flat whatever the directory holds). More than `limit` records
    is `ArchiveTooLarge`; a record that is no record, or a directory whose records do
    not fill it exactly or do not match its declared count, is `invalid_zip`."""
    position, end, count = found.start, found.start + found.size, 0
    while position < end:
        file.seek(position)
        header = file.read(_RECORD_BYTES)
        if len(header) < _RECORD_BYTES or header[:4] != _RECORD:
            raise invalid_zip()
        count += 1
        if limit is not None and count > limit:
            raise ArchiveTooLarge()
        name_len, extra_len, comment_len = struct.unpack("<HHH", header[28:34])
        yield file.read(name_len)
        position += _RECORD_BYTES + name_len + extra_len + comment_len
    if position != end or count != found.entries:
        raise invalid_zip()


def open_archive(file: IO[bytes]) -> zipfile.ZipFile:
    """The archive, once its directory and declared sizes are within the limits; 413
    `import.too_large` above them, 422 `import.invalid_zip` if it is no ZIP."""
    found = directory(file)
    if found.entries > MAX_ENTRIES or found.size > MAX_DIRECTORY_BYTES:
        raise ArchiveTooLarge()
    for _ in entry_names(file, found, MAX_ENTRIES):
        pass
    try:
        file.seek(0)
        archive = zipfile.ZipFile(file)
    except (zipfile.BadZipFile, OSError, ValueError, EOFError, NotImplementedError):
        raise invalid_zip() from None
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
        archive.close()
        raise ArchiveTooLarge()
    return archive


def segments(info: zipfile.ZipInfo) -> list[str] | None:
    """The entry's path as segments, or None if it is unsafe: absolute, with a drive,
    with `..`, or not a regular file (symlink, device)."""
    kind = stat.S_IFMT(info.external_attr >> 16)  # 0 when the tool wrote no type
    if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
        return None
    name = info.filename.replace("\\", "/")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return None
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts) or any("\x00" in p for p in parts):
        return None
    return parts


def read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, max_bytes: int) -> bytes | None:
    """The entry's bytes if they are no more than `max_bytes`; None if it is larger.
    Raises `zipfile.BadZipFile` (and friends) for a damaged or lying entry."""
    with archive.open(info) as handle:
        data = handle.read(max_bytes + 1)
    return data if len(data) <= max_bytes else None


UNREADABLE = (
    zipfile.BadZipFile,
    zlib.error,
    OSError,
    ValueError,
    EOFError,
    NotImplementedError,
    RuntimeError,
)
