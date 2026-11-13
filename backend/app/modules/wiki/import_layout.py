"""How a Markdown ZIP for import is laid out (`transfer.py`): which entries become
pages and at which path, which are attachments of which page, and what is skipped.

`a/b.md` and `a/b/index.md` (or `README.md`) are both the page `a/b`; files under
`_attachments/<page path>/` are that page's attachments; `_attachments/manifest.json`
names the attachments the archive's links point at (`attachment_links.py`).
"""

import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.slug import slugify
from app.modules.wiki import archive, frontmatter
from app.modules.wiki.attachment_links import MANIFEST, InvalidManifest, read_manifest
from app.modules.wiki.models import MAX_DEPTH, MAX_TITLE_CHARS

ATTACHMENTS = "_attachments"
SLUG_CHARS = 74
_INDEX_NAMES = {"index", "readme"}
_MARKDOWN = (".md", ".markdown")


@dataclass(frozen=True, slots=True)
class ArchiveFile:
    """A Markdown file of the archive and the page it becomes."""

    info: zipfile.ZipInfo
    folders: list[str]  # as written in the archive
    slugs: list[str]  # the page path


@dataclass
class Layout:
    files: list[ArchiveFile] = field(default_factory=list)  # parents first
    attached: list[tuple[zipfile.ZipInfo, list[str]]] = field(default_factory=list)
    listed: dict[str, uuid.UUID] = field(default_factory=dict)  # entry → old attachment


def title_of(name: str) -> str:
    words = name.replace("-", " ").replace("_", " ").strip()
    return (words[:1].upper() + words[1:])[:MAX_TITLE_CHARS] or "Seite"


def strings(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def page_title(meta: frontmatter.Meta, body: str, stem: str) -> str:
    """Front matter `title`, else the first heading, else the file name."""
    given = meta.get("title")
    if isinstance(given, str) and given.strip():
        return given.strip()[:MAX_TITLE_CHARS]
    for line in body.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()[:MAX_TITLE_CHARS]
    return title_of(stem)


def layout(zipped: zipfile.ZipFile, skip: Callable[[zipfile.ZipInfo, str], None]) -> Layout:
    """The archive's pages and attachments; `skip` hears of every entry left out."""
    found = Layout()
    for info in zipped.infolist():
        parts = archive.segments(info)
        if parts is None:
            skip(info, "unsafe_path")
            continue
        if info.is_dir() or not parts or parts[0] == "__MACOSX" or parts[-1] == ".DS_Store":
            continue
        if "/".join(parts) == MANIFEST:
            try:
                found.listed = read_manifest(zipped, info)
            except InvalidManifest:
                skip(info, "invalid_manifest")
            continue
        if parts[0] == ATTACHMENTS:
            if len(parts) >= 3:
                found.attached.append((info, parts[1:]))
            else:
                skip(info, "no_page")
            continue
        stem, dot, ext = parts[-1].rpartition(".")
        if not dot or f".{ext.lower()}" not in _MARKDOWN or not stem:
            skip(info, "not_markdown")
            continue
        names = (
            parts[:-1] if stem.lower() in _INDEX_NAMES and len(parts) > 1 else [*parts[:-1], stem]
        )
        if len(names) > MAX_DEPTH:
            skip(info, "too_deep")
            continue
        slugs = [slugify(n, max_length=SLUG_CHARS) for n in names]
        found.files.append(ArchiveFile(info, names, slugs))
    found.files.sort(key=lambda f: len(f.slugs))  # parents first; stable otherwise
    return found
