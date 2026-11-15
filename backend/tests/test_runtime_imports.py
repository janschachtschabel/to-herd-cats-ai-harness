"""Pydantic AI is imported only under `app/runtime/` (plan M5 global constraints): the
rest of the app talks to models through `app.runtime` alone."""

import ast
from pathlib import Path

import app

LIBRARIES = ("pydantic_ai", "pydantic_graph")


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def test_pydantic_ai_only_under_runtime() -> None:
    root = Path(app.__file__).parent
    offenders = {
        f"{path.relative_to(root)}: {name}"
        for path in sorted(root.rglob("*.py"))
        if path.relative_to(root).parts[0] != "runtime"
        for name in _imports(path)
        if name.split(".")[0] in LIBRARIES
    }
    assert offenders == set()


def test_the_runtime_does_use_it() -> None:
    root = Path(app.__file__).parent / "runtime"
    used = {name for path in root.glob("*.py") for name in _imports(path)}
    assert any(name.startswith("pydantic_ai") for name in used)  # the check is not vacuous
