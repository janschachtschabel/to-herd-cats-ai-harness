"""Loading the catalogue: the entries shipped in `app/mcp/catalog/`, then the operator's
in `HERD_MCP_CATALOG_DIR` (`*.yaml`, `*.yml`; hidden files skipped, links followed, as
a Kubernetes ConfigMap mounts them).

Every file is validated on load. A broken file (not YAML, not an entry, too big, an id
already taken) is reported and skipped, never fatal: the problems are listed for the
admin (`GET /api/ai/mcp-catalog/problems`) and logged once per change as
`mcp.catalog_problem` with the file's name and the place and kind of the error,
never the file's content. An operator's entry cannot replace a shipped one.

Files are read again when the directory's listing, a file's size or its modification
time changes, so a new file needs no restart.
"""

import logging
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.core.config import get_settings
from app.modules.mcp_catalog.entry import CatalogEntry
from app.modules.mcp_servers.models import Classification

logger = logging.getLogger(__name__)

SHIPPED_DIR = Path(__file__).resolve().parents[2] / "mcp" / "catalog"
SUFFIXES = (".yaml", ".yml")
MAX_FILES = 100
MAX_FILE_BYTES = 256 * 1024


class Source(StrEnum):
    SHIPPED = "shipped"
    OPERATOR = "operator"


@dataclass(frozen=True)
class Problem:
    source: Source
    file: str  # the file's name, or "" for the directory itself
    reason: str


@dataclass(frozen=True)
class Catalog:
    entries: dict[str, CatalogEntry] = field(default_factory=dict)  # by id, sorted
    problems: tuple[Problem, ...] = ()

    def suggestions(self, entry_id: str | None) -> dict[str, Classification]:
        entry = self.entries.get(entry_id) if entry_id is not None else None
        return dict(entry.tools) if entry is not None else {}


type Signature = tuple[tuple[str, str, int, int], ...]


def _files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.suffix in SUFFIXES and not path.name.startswith(".") and path.is_file()
    )


def _signature(directories: list[tuple[Source, Path]]) -> Signature:
    found: list[tuple[str, str, int, int]] = []
    for source, directory in directories:
        try:
            for path in _files(directory):
                stat = path.stat()
                found.append((source.value, str(path), stat.st_size, stat.st_mtime_ns))
        except OSError:
            found.append((source.value, str(directory), -1, -1))
    return tuple(found)


def _reason(error: ValidationError) -> str:
    """Where and what, never the value (an operator's file may hold anything)."""
    first = error.errors(include_input=False, include_url=False)[0]
    place = ".".join(str(part) for part in first["loc"]) or "entry"
    # The entry's own checks say what is wrong in words of their own (`entry.py`).
    said = f" ({first['ctx']['error']})" if first["type"] == "value_error" else ""
    more = f" (+{error.error_count() - 1} more)" if error.error_count() > 1 else ""
    return f"{place}: {first['type']}{said}{more}"


def _read(path: Path) -> CatalogEntry:
    """The entry in one file; ValueError names what is wrong with it."""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"larger than {MAX_FILE_BYTES} bytes")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise ValueError("not UTF-8") from None
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise ValueError(
            f"not valid YAML (line {mark.line + 1})" if mark else "not valid YAML"
        ) from None
    if not isinstance(data, dict):
        raise ValueError("not a mapping")
    try:
        return CatalogEntry.model_validate(data)
    except ValidationError as error:
        raise ValueError(_reason(error)) from None


def load_directory(
    directory: Path, source: Source
) -> tuple[list[tuple[str, CatalogEntry]], list[Problem]]:
    """The entries (with their file's name) and the problems of one directory."""
    try:
        files = _files(directory)
    except OSError:
        return [], [Problem(source, "", "directory not readable")]
    problems = [Problem(source, p.name, f"more than {MAX_FILES} files") for p in files[MAX_FILES:]]
    entries: list[tuple[str, CatalogEntry]] = []
    for path in files[:MAX_FILES]:
        try:
            entries.append((path.name, _read(path)))
        except (ValueError, OSError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "not readable"
            problems.append(Problem(source, path.name, reason))
    return entries, problems


def load(operator_dir: Path | None) -> Catalog:
    entries: dict[str, CatalogEntry] = {}
    problems: list[Problem] = []
    directories = [(Source.SHIPPED, SHIPPED_DIR)]
    directories += [(Source.OPERATOR, operator_dir)] if operator_dir is not None else []
    for source, directory in directories:
        found, failed = load_directory(directory, source)
        problems += failed
        for name, entry in found:
            if entry.id in entries:
                problems.append(Problem(source, name, f"id {entry.id} already taken"))
            else:
                entries[entry.id] = entry
    for problem in problems:
        logger.warning(
            "mcp.catalog_problem",
            extra={"source": problem.source.value, "file": problem.file, "reason": problem.reason},
        )
    return Catalog(dict(sorted(entries.items())), tuple(problems))


_lock = threading.Lock()
_cached: tuple[tuple[Path | None, Signature], Catalog] | None = None


def catalog() -> Catalog:
    """The catalogue as the files are now; read again only after a change."""
    global _cached  # noqa: PLW0603 (one cache per process, keyed by what it was read from)
    operator_dir = get_settings().mcp_catalog_dir
    directories = [(Source.SHIPPED, SHIPPED_DIR)]
    directories += [(Source.OPERATOR, operator_dir)] if operator_dir is not None else []
    key = (operator_dir, _signature(directories))
    with _lock:
        if _cached is None or _cached[0] != key:
            _cached = (key, load(operator_dir))
        return _cached[1]
