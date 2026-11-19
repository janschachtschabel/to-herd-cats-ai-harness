"""The calendar's libraries each stay behind one boundary (plan M10, tech stack):
`python-dateutil` only in `modules/calendars/recurrence.py` and `recurrence_jump.py`,
`icalendar` only in the package `modules/calendars/ical`, in `app` and in `scripts`
alike."""

import ast
from pathlib import Path

import app
import scripts

DATEUTIL_HOMES = {
    Path("modules/calendars/recurrence.py"),
    Path("modules/calendars/recurrence_jump.py"),
}


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _importers(library: str) -> set[Path]:
    """Every file of `app` and `scripts` that imports `library`, relative to `app`'s
    parent."""
    root = Path(app.__file__).parent
    return {
        path.relative_to(root.parent)
        for top in (root, Path(scripts.__file__).parent)
        for path in sorted(top.rglob("*.py"))
        if any(name.split(".")[0] == library for name in _imports(path))
    }


def test_only_recurrence_imports_dateutil() -> None:
    root = Path(app.__file__).parent
    assert _importers("dateutil") - {Path("app") / home for home in DATEUTIL_HOMES} == set()
    used = _imports(root / "modules/calendars/recurrence.py")
    assert any(name.startswith("dateutil") for name in used)  # the check is not vacuous


def test_only_the_ical_package_imports_icalendar() -> None:
    home = Path("app/modules/calendars/ical")
    found = _importers("icalendar")
    assert {path for path in found if home not in path.parents} == set()
    assert {home / "lines.py", home / "writing.py"} <= found  # the check is not vacuous
