"""The MCP SDK (`mcp`, `mcp_types`) is imported only under `app/mcp/` (plan M8, global
constraints): the rest of the app reaches MCP servers through `app.mcp` alone."""

from pathlib import Path

import app
from tests.test_runtime_imports import _imports

LIBRARIES = ("mcp", "mcp_types")


def test_the_mcp_sdk_only_under_app_mcp() -> None:
    root = Path(app.__file__).parent
    offenders = {
        f"{path.relative_to(root)}: {name}"
        for path in sorted(root.rglob("*.py"))
        if path.relative_to(root).parts[0] != "mcp"
        for name in _imports(path)
        if name.split(".")[0] in LIBRARIES
    }
    assert offenders == set()


def test_app_mcp_does_use_it() -> None:
    root = Path(app.__file__).parent / "mcp"
    used = {name for path in root.rglob("*.py") for name in _imports(path)}
    assert any(name.split(".")[0] == "mcp" for name in used)  # the check is not vacuous
