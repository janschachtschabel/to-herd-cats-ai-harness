"""Hard rule 3 for M8's modules (module review M8 1, finding 11): SQL lives in
repositories. Their services, flows and handlers build no statement of their own;
`tokens/reach.py` builds filters for repositories (like `core/access.py`) and may."""

import ast
from pathlib import Path

import app

MODULES = ("oauth", "tokens", "connectors", "mcp_servers", "mcp_tools")
STATEMENTS = {"select", "text", "update", "delete", "insert"}
FILTER_BUILDERS = {"tokens/reach.py"}


def _statement_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy")
        for alias in node.names
        if alias.name in STATEMENTS
    }


def test_no_sql_outside_repositories() -> None:
    root = Path(app.__file__).parent / "modules"
    offenders = {
        f"{rel}: {sorted(names)}"
        for module in MODULES
        for path in sorted((root / module).rglob("*.py"))
        if "repository" not in path.name and path.name != "models.py"
        if (rel := path.relative_to(root).as_posix()) not in FILTER_BUILDERS
        if (names := _statement_imports(path))
    }
    assert offenders == set()
