"""The catalogue (plan M8 decision 10, task 9): entries shipped as files under
`app/mcp/catalog/` (GitHub, GitLab) and the operator's in `HERD_MCP_CATALOG_DIR`,
validated on load; a broken file is reported and skipped, never fatal."""

import logging
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.modules.mcp_catalog.entry import CatalogEntry, render
from app.modules.mcp_catalog.loader import SHIPPED_DIR, Source, catalog, load, load_directory
from scripts.check_mcp_catalog import main as check_main
from tests.factories_catalog import CATALOG, entry, oauth_option, write_entry
from tests.factories_dms import People

SECRET = "pw-IN-a-broken-FILE-77"


def test_the_shipped_entries_load_clean() -> None:
    entries, problems = load_directory(SHIPPED_DIR, Source.SHIPPED)
    assert problems == []
    by_id = {e.id: e for _, e in entries}
    assert set(by_id) == {"github", "gitlab"}
    github, gitlab = by_id["github"], by_id["gitlab"]
    assert github.url == "https://api.githubcopilot.com/mcp/" and github.base_url is None
    assert [o.kind for o in github.auth] == ["oauth", "bearer"]
    oauth = github.auth[0].oauth
    assert oauth is not None and oauth.revocation_endpoint is None  # GitHub has none
    assert gitlab.base_url is not None and gitlab.base_url.default == "https://gitlab.com"
    assert render(gitlab.url, "https://git.example") == "https://git.example/api/v4/mcp"
    spec = gitlab.auth[0].oauth
    assert spec is not None and spec.scopes == "mcp" and spec.resource is True
    assert render(spec.revocation_endpoint or "", "https://g.example") == (
        "https://g.example/oauth/revoke"
    )
    for item in (github, gitlab):
        assert set(item.connector_scopes) == {"personal", "shared"}
        assert item.docs and item.tools and all(o.note for o in item.auth)
        assert {"read", "write"} == set(item.tools.values())


def test_a_broken_operator_file_is_skipped_and_reported(
    catalog_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_entry(catalog_dir, entry("https://mcp.example/mcp"), "good.yaml")
    (catalog_dir / "broken.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    write_entry(catalog_dir, entry(f"https://user:{SECRET}@mcp.example/mcp", id="b"), "bad.yml")
    write_entry(catalog_dir, entry("https://mcp.example/x", id="github"), "dup.yaml")
    (catalog_dir / "list.yaml").write_text("- one\n- two\n", encoding="utf-8")
    (catalog_dir / "big.yaml").write_text("# " + "x" * 300_000, encoding="utf-8")
    (catalog_dir / "latin.yaml").write_bytes(b"name: \xe4\n")
    (catalog_dir / ".hidden.yaml").write_text("id: [", encoding="utf-8")
    (catalog_dir / "notes.txt").write_text("id: [", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        loaded = load(catalog_dir)
    assert list(loaded.entries) == ["github", "gitlab", "tracker"]
    reasons = {p.file: p.reason for p in loaded.problems}
    assert all(p.source == Source.OPERATOR for p in loaded.problems)
    assert reasons == {
        "bad.yml": "entry: value_error (an https address with a host is needed)",
        "big.yaml": "larger than 262144 bytes",
        "broken.yaml": "not valid YAML (line 2)",
        "dup.yaml": "id github already taken",
        "latin.yaml": "not UTF-8",
        "list.yaml": "not a mapping",
    }
    logged = [r for r in caplog.records if r.getMessage() == "mcp.catalog_problem"]
    assert len(logged) == 6
    assert SECRET not in caplog.text and SECRET not in repr(loaded.problems)


def test_a_missing_directory_is_a_problem_not_a_crash(tmp_path: Path) -> None:
    loaded = load(tmp_path / "nowhere")
    assert list(loaded.entries) == ["github", "gitlab"]
    assert [(p.file, p.reason) for p in loaded.problems] == [("", "directory not readable")]


def test_a_new_file_is_read_without_a_restart(catalog_dir: Path) -> None:
    assert "tracker" not in catalog().entries
    write_entry(catalog_dir, entry("https://mcp.example/mcp"))
    assert catalog().entries["tracker"].name == "Tracker"
    assert catalog() is catalog()  # unchanged files are not read again
    write_entry(catalog_dir, entry("https://mcp.example/mcp", name="Renamed tracker"))
    assert catalog().entries["tracker"].name == "Renamed tracker"


@pytest.mark.parametrize(
    "fields",
    [
        {"url": "http://mcp.example/mcp"},
        {"url": "https://mcp.example/mcp?token=1"},
        {"url": "{base_url}/mcp"},  # no base_url
        {"url": "{host}/mcp", "base_url": {"default": "https://a.example"}},
        {"base_url": {"default": "http://a.example"}},
        {"id": "Not An Id"},
        {"connector_scopes": ["shared", "shared"]},
        {"connector_scopes": ["shared"], "auth": []},
        {"connector_scopes": ["none"]},  # auth without a scope that uses it
        {"auth": [{"kind": "oauth"}]},  # no endpoints
        {"auth": [{"kind": "bearer", "oauth": oauth_option()["oauth"]}]},
        {"auth": [{"kind": "header"}]},  # no header name
        {"auth": [{"kind": "header", "header_name": "Host"}]},
        {"auth": [{"kind": "bearer"}, {"kind": "bearer"}]},
        {"tools": {"x": "approve"}},
        {"client_secret": "never in an entry"},
        {"description": {"de": "nur Deutsch"}},
    ],
)
def test_entries_are_validated(fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CatalogEntry.model_validate({**entry("https://mcp.example/mcp"), **fields})


def test_a_template_entry_is_valid() -> None:
    data = entry(
        "{base_url}/api/mcp",
        base_url={"default": "https://git.example"},
        auth=[oauth_option(), {"kind": "header", "header_name": "PRIVATE-TOKEN"}],
    )
    made = CatalogEntry.model_validate(data)
    assert made.option("oauth") is not None and made.option("bearer") is None


async def test_only_ai_managers_reach_the_catalogue(ai_people: People) -> None:
    for who in ("alice", "gast"):
        client = getattr(ai_people, who)
        for method, url, body in (
            ("GET", CATALOG, None),
            ("GET", f"{CATALOG}/problems", None),
            ("GET", f"{CATALOG}/github", None),
            ("POST", f"{CATALOG}/github/install", {"connector_scope": "none"}),
        ):
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (who, url, response.text)
            assert response.json()["error"]["code"] == "ai.not_found"


async def test_the_catalogue_is_listed_page_by_page(ai_people: People, catalog_dir: Path) -> None:
    write_entry(catalog_dir, entry("https://mcp.example/mcp"))
    (catalog_dir / "a.yaml").write_text("{", encoding="utf-8")
    (catalog_dir / "b.yaml").write_text("[", encoding="utf-8")
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = (await ai_people.admin.get(CATALOG, params=params)).json()
        seen += [e["id"] for e in page["items"]]
        if not (cursor := page["next_cursor"]):
            break
    assert seen == ["github", "gitlab", "tracker"]
    github = (await ai_people.admin.get(f"{CATALOG}/github")).json()
    assert github["auth"][0]["oauth"]["scopes"] == "repo read:org"
    assert github["tools"]["merge_pull_request"] == "write"
    missing = await ai_people.admin.get(f"{CATALOG}/nothing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "mcp_catalog.not_found"
    first = (await ai_people.admin.get(f"{CATALOG}/problems", params={"limit": 1})).json()
    assert first["items"] == [
        {"source": "operator", "file": "a.yaml", "reason": first["items"][0]["reason"]}
    ]
    params = {"limit": 1, "cursor": first["next_cursor"]}
    second = (await ai_people.admin.get(f"{CATALOG}/problems", params=params)).json()
    assert [p["file"] for p in second["items"]] == ["b.yaml"] and second["next_cursor"] is None
    bad = await ai_people.admin.get(CATALOG, params={"cursor": "%%%"})
    assert bad.status_code == 422


def test_the_check_script_passes_the_shipped_entries_and_fails_a_broken_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_main([]) == 0
    assert "github" in capsys.readouterr().out
    write_entry(tmp_path, entry("https://mcp.example/mcp"))
    write_entry(tmp_path, entry("https://mcp.example/mcp", id="gitlab"), "mine.yaml")
    (tmp_path / "broken.yaml").write_text("id: [", encoding="utf-8")
    assert check_main([str(tmp_path)]) == 1
    printed = capsys.readouterr()
    assert "tracker" in printed.out and "broken.yaml: not valid YAML" in printed.err
    assert "mine.yaml: id gitlab already taken" in printed.err
    assert check_main([str(tmp_path / "empty-nowhere")]) == 1
