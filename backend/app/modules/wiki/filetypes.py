"""What an uploaded file is, decided by its content (spec 9: no SVG, no HTML).

Binary formats by their magic bytes; Office files and ZIP by the archive's entries;
text (TXT, Markdown, CSV, JSON) when it is all valid UTF-8 without NUL and does not
begin like markup a browser would run (only the first bytes are looked at; nothing is
parsed whole, JSON included: it is served as a download like any text). The file
name's extension must then belong to what was found: a `bild.png` that is HTML is
refused as HTML, and a PNG named `seite.html` is refused as a mismatch.
"""

from dataclasses import dataclass
from typing import IO

from app.core.errors import AppError
from app.modules.wiki import archive


class UnsupportedType(AppError):
    status_code = 415
    code = "attachment.type_not_allowed"


@dataclass(frozen=True, slots=True)
class FileType:
    mime: str
    extensions: frozenset[str]
    inline: bool = False  # raster images may be shown in the page


def _t(mime: str, *extensions: str, inline: bool = False) -> FileType:
    return FileType(mime, frozenset(extensions), inline)


PNG = _t("image/png", "png", inline=True)
JPEG = _t("image/jpeg", "jpg", "jpeg", inline=True)
GIF = _t("image/gif", "gif", inline=True)
WEBP = _t("image/webp", "webp", inline=True)
PDF = _t("application/pdf", "pdf")
ZIP = _t("application/zip", "zip")
DOCX = _t("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx")
XLSX = _t("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")
PPTX = _t("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx")
TEXT = _t("text/plain", "txt")
MARKDOWN = _t("text/markdown", "md", "markdown")
CSV = _t("text/csv", "csv")
JSON = _t("application/json", "json")
TEXT_TYPES = (TEXT, MARKDOWN, CSV, JSON)

_ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
_OFFICE = {"word/": DOCX, "xl/": XLSX, "ppt/": PPTX}
# Markup a browser would render or run, at the start of a text file.
_MARKUP = (b"<html", b"<svg", b"<script", b"<!doctype", b"<?xml", b"<body", b"<head", b"<iframe")
_MARKUP_WINDOW = 1024


def extension_of(filename: str) -> str:
    _, dot, ext = filename.rpartition(".")
    return ext.lower() if dot else ""


def detect(head: bytes, is_text: bool, file: IO[bytes], filename: str) -> FileType:
    """The type of the content in `file` (seekable; `head` are its first bytes), as
    allowed for `filename`; `UnsupportedType` (415) otherwise."""
    if head[:4] in _ZIP_MAGIC:  # an archive, or nothing allowed (never text)
        found = _archive(file)
    else:
        found = _binary(head) or (_text(head, filename) if is_text else None)
    if found is None:
        raise UnsupportedType()
    if extension_of(filename) not in found.extensions:
        raise UnsupportedType(code="attachment.type_mismatch")
    return found


def _binary(head: bytes) -> FileType | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return GIF
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head.startswith(b"%PDF-"):
        return PDF
    return None


def _archive(file: IO[bytes]) -> FileType | None:
    """ZIP, or the Office format whose parts it holds (names only, read one directory
    record at a time; nothing is unpacked). A broken archive is nothing allowed."""
    office: set[FileType] = set()
    typed = False
    try:
        found = archive.directory(file)
        for raw in archive.entry_names(file, found, limit=None):
            name = raw.decode("utf-8", "replace")
            typed = typed or name == "[Content_Types].xml"
            office.update(kind for prefix, kind in _OFFICE.items() if name.startswith(prefix))
    except (AppError, OSError, ValueError):
        return None
    if typed:
        for kind in _OFFICE.values():  # the first that fits, as before
            if kind in office:
                return kind
    return ZIP


def _text(head: bytes, filename: str) -> FileType | None:
    start = head.removeprefix(b"\xef\xbb\xbf").lstrip()[:_MARKUP_WINDOW].lower()
    if any(marker in start for marker in _MARKUP):
        return None
    ext = extension_of(filename)
    return next((t for t in TEXT_TYPES if ext in t.extensions), TEXT)
