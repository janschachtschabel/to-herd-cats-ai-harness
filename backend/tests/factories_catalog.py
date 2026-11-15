"""Catalogue fixtures: `catalog_dir` (an empty `HERD_MCP_CATALOG_DIR` for the test) and
helpers that write an operator's entry there, pointing at the MCP and OAuth stubs."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from app.core.config import get_settings

CATALOG = "/api/ai/mcp-catalog"


@pytest.fixture
def catalog_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "catalog"
    directory.mkdir()
    monkeypatch.setattr(get_settings(), "mcp_catalog_dir", directory)
    return directory


def entry(url: str, **fields: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "tracker",
        "name": "Tracker",
        "description": {"de": "Ein Tracker.", "en": "A tracker."},
        "url": url,
        "connector_scopes": ["none", "shared", "personal"],
        "auth": [{"kind": "bearer"}],
        "tools": {"search_issues": "write", "create_issue": "read"},
    }
    data.update(fields)
    return data


def oauth_option(**fields: Any) -> dict[str, Any]:
    """An `oauth` sign-in with its endpoints below `{base_url}` (the stub's, as the
    entry's `base_url` names it)."""
    spec = {
        "authorization_endpoint": "{base_url}/authorize",
        "token_endpoint": "{base_url}/token",
        "revocation_endpoint": "{base_url}/revoke",
        "scopes": "mcp read",
        **fields,
    }
    return {"kind": "oauth", "oauth": spec}


def write_entry(directory: Path, data: dict[str, Any], file: str = "tracker.yaml") -> Path:
    path = directory / file
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path
