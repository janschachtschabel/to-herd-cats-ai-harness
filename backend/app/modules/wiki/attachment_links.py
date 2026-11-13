"""Links to attachments across an export and import (spec 9).

Pages link their attachments as `/api/attachments/<id>`. An exported archive lists
which attachment each file under `_attachments/` was, in `_attachments/manifest.json`
(`{"attachments": {"<entry name>": "<attachment id>"}}`); the import points links to
the attachments it brought in at their new ids. Links to anything else (attachments
the archive does not carry or the import refused, other hosts) stay as they were.
"""

import json
import re
import uuid
import zipfile

from app.modules.wiki import archive

MANIFEST = "_attachments/manifest.json"
MANIFEST_MAX_BYTES = 1024 * 1024

# Root-relative only: a link with a host in front belongs to another installation.
_LINK = re.compile(
    r"(?<![\w/.:-])(/api/attachments/)"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?![\w-])"
)


class InvalidManifest(ValueError):
    """Not a manifest this code wrote."""


def manifest_json(entries: dict[str, uuid.UUID]) -> str:
    return json.dumps(
        {"attachments": {name: str(i) for name, i in sorted(entries.items())}}, indent=1
    )


def read_manifest(zipped: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict[str, uuid.UUID]:
    """Entry name → the attachment id it had; `InvalidManifest` for anything else
    (too large, not JSON, wrong shape, an id that is no UUID)."""
    try:
        raw = archive.read_entry(zipped, info, MANIFEST_MAX_BYTES)
    except archive.UNREADABLE:
        raise InvalidManifest from None
    if raw is None:
        raise InvalidManifest
    try:
        data = json.loads(raw.decode("utf-8"))
        listed = data["attachments"]
        if not isinstance(listed, dict):
            raise InvalidManifest
        return {str(name): uuid.UUID(str(old)) for name, old in listed.items()}
    except (UnicodeDecodeError, ValueError, TypeError, KeyError):
        raise InvalidManifest from None


def rewrite_links(markdown: str, new_ids: dict[uuid.UUID, uuid.UUID]) -> str:
    """`markdown` with links to the old ids in `new_ids` pointing at the new ones."""
    if not new_ids or "/api/attachments/" not in markdown:
        return markdown

    def replace(match: re.Match[str]) -> str:
        new = new_ids.get(uuid.UUID(match.group(2)))
        return f"{match.group(1)}{new}" if new else match.group(0)

    return _LINK.sub(replace, markdown)
