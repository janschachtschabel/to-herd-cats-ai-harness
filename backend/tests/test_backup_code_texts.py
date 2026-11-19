"""Every code the backup API can answer has a text in `de` and `en` (review M9b final,
F2-5: the likeliest failures of "Einspielen" showed the raw code).

Codes reach the administration two ways:
- as a code shown by `frontend/src/features/backup/codes.ts` (a check's problems and
  warnings, a failed restore's code, a backup run's error): `backup.codes.<code>`;
  that is every code-like literal of `app/ops` and `app/modules/backups` except the
  HTTP answers, the audit actions and the log events below;
- as an HTTP error (`code=` of the service's exceptions, `ReplaceBusy`):
  `errors.<code>`, shown by `lib/errors.ts`.

A new code fails this test until it has its texts (or, if it is an audit action or a
log event, is named in NOT_SHOWN)."""

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
LOCALES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales"
SOURCES = [*sorted((APP / "ops").glob("*.py")), *sorted((APP / "modules/backups").glob("*.py"))]
SOURCES.append(APP / "core" / "db_roles.py")
_CODE = re.compile(r"(archive|restore|backup)\.[a-z_]+")
# Made at run time (`swap.py`: `restore.swap_{outcome}` for an outcome that is not
# SWAPPED or KEPT).
DYNAMIC = {"restore.swap_broken", "restore.swap_unknown"}
# Audit actions and log events: written down, never shown as a code.
NOT_SHOWN = {
    "backup.checked",
    "backup.created",
    "backup.downloaded",
    "backup.interrupted_found",
    "backup.job_failed",
    "backup.leftovers_removed",
    "backup.lock_lost",
    "backup.lock_release_failed",
    "backup.offsite_failed",
    "backup.replace_failed",
    "backup.replace_refused",
    "backup.replaced",
    "backup.request_done",
    "backup.request_gone",
    "backup.requested",
    "backup.restore_failed",
    "backup.restore_requested",
    "backup.restore_uncertain",
    "backup.restore_uncertain_unrecorded",
    "backup.restored",
    "backup.tool_failed",
    "backup.uploaded",
    "backup.refused",
    "backup.database_unavailable",
    "backup.no_organization",
}


def _merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for key, value in b.items():
        both = isinstance(value, dict) and isinstance(out.get(key), dict)
        out[key] = _merge(out[key], value) if both else value
    return out


def _texts(locale: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in sorted((LOCALES / locale).glob("*.json")):
        merged = _merge(merged, json.loads(path.read_text(encoding="utf-8")))
    return merged


def _has(texts: dict[str, Any], key: str) -> bool:
    node: Any = texts
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return isinstance(node, str) and bool(node)


def _code_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.JoinedStr):  # f"restore.env_missing:{name}": before ':'
        first = node.values[0] if node.values else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            return None
        match = _CODE.match(first.value)
        return match.group(0) if match and first.value[match.end() :][:1] == ":" else None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        match = _CODE.fullmatch(node.value)
        return match.group(0) if match else None
    return None


def _codes() -> tuple[set[str], set[str]]:
    """(shown codes, HTTP codes) of the sources."""
    shown: set[str] = set(DYNAMIC)
    http: set[str] = set()
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                skip |= {id(part) for part in node.values}
            answer: ast.AST | None = None
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if name == "ReplaceBusy" and node.args:
                    answer = node.args[0]
                for keyword in node.keywords:
                    if keyword.arg == "code":
                        answer = keyword.value
            elif isinstance(node, ast.Assign) and [getattr(t, "id", "") for t in node.targets] == [
                "code"
            ]:
                answer = node.value  # an exception class's `code = "..."`
            if answer is not None and (code := _code_of(answer)):
                http.add(code)
                skip.add(id(answer))
        for node in ast.walk(tree):
            if id(node) not in skip and (code := _code_of(node)) and code not in NOT_SHOWN:
                shown.add(code)
    return shown, http


@pytest.mark.parametrize("locale", ["de", "en"])
def test_every_code_of_the_backup_api_has_a_text(locale: str) -> None:
    texts = _texts(locale)
    shown, http = _codes()
    assert "restore.swap_failed" in shown and "backup.busy" in http  # the scan works
    missing = sorted(c for c in shown if not _has(texts, f"backup.codes.{c}"))
    missing += sorted(f"errors.{c}" for c in http if not _has(texts, f"errors.{c}"))
    assert missing == [], f"{locale}: no text for {missing}"
