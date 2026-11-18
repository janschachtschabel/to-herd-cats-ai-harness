"""The calendar's libraries each stay behind one boundary (plan M10, tech stack):
`python-dateutil` only in `modules/calendars/recurrence.py` and `recurrence_jump.py`,
in `app` and in `scripts` alike."""

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


def test_only_recurrence_imports_dateutil() -> None:
    root = Path(app.__file__).parent
    backend = root.parent
    offenders = {
        f"{path.relative_to(backend)}: {name}"
        for top in (root, Path(scripts.__file__).parent)
        for path in sorted(top.rglob("*.py"))
        if path.relative_to(backend) not in {Path("app") / home for home in DATEUTIL_HOMES}
        for name in _imports(path)
        if name.split(".")[0] == "dateutil"
    }
    assert offenders == set()
    used = _imports(root / "modules/calendars/recurrence.py")
    assert any(name.startswith("dateutil") for name in used)  # the check is not vacuous
