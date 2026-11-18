"""Writing and checking backup archives (plan M9 decision 3, format 1).

An archive is an uncompressed tar file (PAX headers) with, in this order,
`herd/FORMAT` (`1`), `herd/db.dump`, `herd/files/<storage key>` for every file and
last `herd/manifest.json`; next to it `<name>.manifest.json`, the same manifest plus
`archive_sha256`. The writer streams: it never holds a member in memory, computes each
member's SHA-256 and the archive's while writing, and writes to a hidden `.part` file
(mode 0600, its directory 0700 when it creates it) renamed into place by `finish`, so
an archive under its name is always whole.

`verify_archive` reads an archive back and names its problems as codes, never its
content: `archive.checksum` (the sidecar's `archive_sha256` does not match),
`archive.format_unknown`, `archive.member_missing`, `archive.member_checksum` (a
member differs from the manifest, or is not in it) and `archive.truncated`. Without a
sidecar (an archive uploaded on its own) the members are checked against the inner
manifest alone.
"""

import asyncio
import dataclasses
import hashlib
import json
import os
import tarfile
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import IO, BinaryIO

from app.ops.manifest import FORMAT, Manifest, ManifestInvalid, Member

PREFIX = "herd/"
FORMAT_MEMBER = "FORMAT"
MANIFEST_MEMBER = "manifest.json"
DUMP_MEMBER = "db.dump"
FILES_PREFIX = "files/"
SIDECAR_SUFFIX = ".manifest.json"
CHUNK = 1024 * 1024
_BLOCK = tarfile.BLOCKSIZE
_RECORD = tarfile.RECORDSIZE


class ArchiveError(Exception):
    """Writing the archive failed; `code` says why (no content, no path)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def sidecar_of(path: Path) -> Path:
    return path.with_name(path.name.removesuffix(".tar") + SIDECAR_SUFFIX)


def private_dir(directory: Path) -> None:
    """Create `directory` (mode 0700) unless it exists; an existing one is the
    operator's (a mounted volume) and keeps its mode."""
    if not directory.is_dir():
        directory.mkdir(mode=0o700, parents=True)


class ArchiveWriter:
    """Members go in the order they are added; `finish` adds the manifest and ends
    the archive, `abort` removes what was written."""

    def __init__(self, path: Path) -> None:
        private_dir(path.parent)
        if path.exists():
            raise ArchiveError("archive.exists")
        self.path = path
        self.members: dict[str, Member] = {}
        self._part = path.with_name(f".{path.name}.part")
        fd = os.open(self._part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self._out: BinaryIO = os.fdopen(fd, "wb")
        self._hash = hashlib.sha256()
        self._written = 0
        self._header(FORMAT_MEMBER, len(f"{FORMAT}\n"))
        self._data(f"{FORMAT}\n".encode())
        self._pad()

    async def add_file(self, name: str, source: Path) -> None:
        handle = await asyncio.to_thread(source.open, "rb")
        try:
            size = os.fstat(handle.fileno()).st_size
            await self.add_stream(name, size, read_chunks(handle))
        finally:
            handle.close()

    async def add_stream(self, name: str, size: int, chunks: AsyncIterator[bytes]) -> None:
        """A member of `size` bytes; other than `size` is `archive.member_size`."""
        if name in self.members or name in (FORMAT_MEMBER, MANIFEST_MEMBER):
            raise ArchiveError("archive.member_twice")
        self._header(name, size)
        member = hashlib.sha256()
        count = 0
        async for chunk in chunks:
            count += len(chunk)
            if count > size:
                raise ArchiveError("archive.member_size")
            member.update(chunk)
            await asyncio.to_thread(self._data, chunk)
        if count != size:
            raise ArchiveError("archive.member_size")
        self._pad()
        self.members[name] = Member(sha256=member.hexdigest(), size=size)

    async def finish(self, manifest: Manifest) -> str:
        """Add the manifest (with the members' checksums), end the archive, put it and
        its sidecar in place; the archive's SHA-256."""
        final = dataclasses.replace(manifest, members=dict(self.members))
        data = final.to_json()
        self._header(MANIFEST_MEMBER, len(data))
        self._data(data)
        self._pad()
        self._data(b"\0" * (2 * _BLOCK))
        if self._written % _RECORD:
            self._data(b"\0" * (_RECORD - self._written % _RECORD))
        await asyncio.to_thread(_sync_close, self._out)
        os.replace(self._part, self.path)
        archive_sha256 = self._hash.hexdigest()
        write_sidecar(self.path, data, archive_sha256)
        return archive_sha256

    def abort(self) -> None:
        self._out.close()
        self._part.unlink(missing_ok=True)

    def _header(self, name: str, size: int) -> None:
        info = tarfile.TarInfo(PREFIX + name)
        info.size = size
        info.mode = 0o600
        info.mtime = int(time.time())
        self._data(info.tobuf(tarfile.PAX_FORMAT, "utf-8", "surrogateescape"))

    def _data(self, data: bytes) -> None:
        self._out.write(data)
        self._hash.update(data)
        self._written += len(data)

    def _pad(self) -> None:
        if self._written % _BLOCK:
            self._data(b"\0" * (_BLOCK - self._written % _BLOCK))


def write_sidecar(path: Path, manifest: bytes, archive_sha256: str) -> None:
    """The sidecar of the archive at `path`: its manifest (JSON) plus `archive_sha256`
    (also for an archive uploaded on its own, `modules/backups/archives.py`)."""
    sidecar = json.loads(manifest)
    sidecar["archive_sha256"] = archive_sha256
    _write_private(sidecar_of(path), json.dumps(sidecar, sort_keys=True, indent=2))
    _sync_dir(path.parent)


def read_sidecar(path: Path) -> tuple[Manifest, str]:
    """The sidecar's manifest and `archive_sha256`; `ManifestInvalid` if it has none."""
    try:
        data = json.loads(sidecar_of(path).read_bytes())
        archive_sha256 = data.pop("archive_sha256")
    except (ValueError, KeyError, AttributeError, TypeError):
        raise ManifestInvalid("not a sidecar of this format") from None
    if not isinstance(archive_sha256, str):
        raise ManifestInvalid("not a sidecar of this format")
    return Manifest.from_json(json.dumps(data).encode()), archive_sha256


def verify_archive(path: Path) -> list[str]:
    """The archive's problems as codes, in a fixed order; empty when it is good."""
    problems: list[str] = []
    if sidecar_of(path).exists():
        try:
            _, expected = read_sidecar(path)
        except ManifestInvalid:
            return ["archive.format_unknown"]
        if _file_sha256(path) != expected:
            problems.append("archive.checksum")
    seen, inner, truncated = _read_members(path)
    if inner.get(FORMAT_MEMBER) != f"{FORMAT}\n".encode():
        return [*problems, "archive.format_unknown"]
    manifest_data = inner.get(MANIFEST_MEMBER)
    if manifest_data is None:
        return [*problems, "archive.member_missing" if not truncated else "archive.truncated"]
    try:
        manifest = Manifest.from_json(manifest_data)
    except ManifestInvalid:
        return [*problems, "archive.format_unknown"]
    if manifest.format != FORMAT:
        return [*problems, "archive.format_unknown"]
    if any(name not in seen for name in manifest.members):
        problems.append("archive.member_missing")
    extra = set(seen) - set(manifest.members)
    if extra or any(seen[n] != m for n, m in manifest.members.items() if n in seen):
        problems.append("archive.member_checksum")
    if truncated:
        problems.append("archive.truncated")
    return problems


def _read_members(path: Path) -> tuple[dict[str, Member | None], dict[str, bytes], bool]:
    """Every member's checksum (None for one that is not a plain file or comes twice),
    the content of FORMAT and the manifest, and whether the archive ends early."""
    seen: dict[str, Member | None] = {}
    inner: dict[str, bytes] = {}
    try:
        with tarfile.open(path, "r:") as tar:
            for info in tar:
                name = info.name.removeprefix(PREFIX)
                if not info.name.startswith(PREFIX) or not info.isreg() or name in seen:
                    seen[name] = None
                    continue
                if name in (FORMAT_MEMBER, MANIFEST_MEMBER):
                    handle = tar.extractfile(info)
                    inner[name] = handle.read() if handle is not None else b""
                    continue
                seen[name] = _member_sha256(tar, info)
            end = tar.offset
    except (tarfile.TarError, EOFError, OSError):
        return seen, inner, True
    with path.open("rb") as raw:
        raw.seek(end)
        tail = raw.read(2 * _BLOCK)
    return seen, inner, tail != b"\0" * (2 * _BLOCK)


def _member_sha256(tar: tarfile.TarFile, info: tarfile.TarInfo) -> Member:
    handle = tar.extractfile(info)
    digest = hashlib.sha256()
    if handle is not None:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return Member(sha256=digest.hexdigest(), size=info.size)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


async def read_chunks(handle: IO[bytes]) -> AsyncIterator[bytes]:
    while chunk := await asyncio.to_thread(handle.read, CHUNK):
        yield chunk


def _sync_close(handle: BinaryIO) -> None:
    handle.flush()
    os.fsync(handle.fileno())
    handle.close()


def _write_private(path: Path, text: str) -> None:
    part = path.with_name(f".{path.name}.part")
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, path)


def _sync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
