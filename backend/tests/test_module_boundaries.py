"""Module boundaries (review M4 P9): tickets build on messaging (a ticket's thread,
timeline and notifications), so messaging never imports tickets; what it needs of
them comes through `messaging/ticket_hooks.py`, which tickets register."""

import ast
from pathlib import Path

import app.modules.messaging as messaging_package
from app.modules.messaging.ticket_hooks import ticket_hooks


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_messaging_never_imports_tickets() -> None:
    root = Path(messaging_package.__file__).parent
    offenders = {
        f"{path.name}: {name}"
        for path in sorted(root.glob("*.py"))
        for name in _imports(path)
        if name == "app.modules.tickets" or name.startswith("app.modules.tickets.")
    }
    assert offenders == set()


def test_tickets_register_what_messaging_reads_of_them() -> None:
    import app.modules.tickets  # noqa: F401 -- the package registers its hooks

    hooks = ticket_hooks()
    assert hooks.key(12) == "HC-12"
