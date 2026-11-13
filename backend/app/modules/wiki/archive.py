"""Reading an uploaded ZIP without trusting it.

- Entry count: read from the end-of-central-directory record before the directory is
  parsed, so an archive with millions of entries is refused without building them.
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
from typing import IO

from app.core.errors import AppError, ValidationFailed

MAX_ENTRIES = 2000
MAX_UNPACKED_BYTES = 200 * 1024 * 1024

_EOCD = b"PK\x05\x06"
_EOCD64_LOCATOR = b"PK\x06\x07"
_EOCD64 = b"PK\x06\x06"
_TAIL = 22 + 0xFFFF  # the record plus the longest comment


class ArchiveTooLarge(AppError):
    status_code = 413
    code = "import.too_large"


def invalid_zip() -> ValidationFailed:
    return ValidationFailed(code="import.invalid_zip")


def declared_entries(file: IO[bytes]) -> int:
    """The number of entries the archive's last end record states (zip64 included)."""
    file.seek(0, io.SEEK_END)
    size = file.tell()
    file.seek(max(0, size - _TAIL))
    tail = file.read()
    at = tail.rfind(_EOCD)
    if at < 0 or len(tail) - at < 22:
        raise invalid_zip()
    entries = struct.unpack("<H", tail[at + 10 : at + 12])[0]
    if entries != 0xFFFF:
        return int(entries)
    locator = tail.rfind(_EOCD64_LOCATOR, 0, at)
    if locator < 0 or at - locator < 20:
        raise invalid_zip()
    offset = struct.unpack("<Q", tail[locator + 8 : locator + 16])[0]
    file.seek(offset)
    record = file.read(56)
    if len(record) < 56 or record[:4] != _EOCD64:
        raise invalid_zip()
    return int(struct.unpack("<Q", record[32:40])[0])


def open_archive(file: IO[bytes]) -> zipfile.ZipFile:
    """The archive, once its count and declared sizes are within the limits; 413
    `import.too_large` above them, 422 `import.invalid_zip` if it is no ZIP."""
    if declared_entries(file) > MAX_ENTRIES:
        raise ArchiveTooLarge()
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
