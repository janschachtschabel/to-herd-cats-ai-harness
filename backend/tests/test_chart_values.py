"""The chart's values files keep to values.schema.json, and every `@param` in values.yaml
has a schema entry and every schema entry a `@param` (plan M9 Task 7). The check is
deploy/helm/scripts/check_values.py; it needs no helm, so it runs here and in CI."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

CHART = Path(__file__).resolve().parents[2] / "deploy" / "helm" / "to-herd-cats-ai"
SCRIPT = CHART.parent / "scripts" / "check_values.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_values", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in deploy/
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


check_values = _module()


def test_the_chart_values_and_schema_agree(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_values.main([str(CHART)]) == 0
    out = capsys.readouterr().out
    assert "values.yaml" in out
    assert "full-values.yaml" in out and "production-values.yaml" in out


def test_every_ci_values_file_is_checked() -> None:
    files = {path.name for path in check_values.values_files(CHART)}
    assert files >= {"values.yaml", "production-values.yaml", "full-values.yaml"}
    assert files == {"values.yaml"} | {path.name for path in (CHART / "ci").glob("*-values.yaml")}


def test_a_wrong_values_file_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chart = _copy(tmp_path)
    (chart / "ci" / "wrong-values.yaml").write_text(
        "api:\n  autoscaling:\n    enabled: true\n    maxReplicas: 0\n  env:\n"
        "    HERD_SECRET_KEY: plain\nbackup:\n  keepDaily: -1\nunknown: 1\n",
        encoding="utf-8",
    )
    assert check_values.main([str(chart)]) == 1
    out = capsys.readouterr().out
    assert "wrong-values.yaml: api.autoscaling.maxReplicas" in out
    assert "wrong-values.yaml: backup.keepDaily" in out
    assert "wrong-values.yaml: api.env" in out and "HERD_SECRET_KEY" in out
    assert "wrong-values.yaml: (root)" in out and "unknown" in out


def test_a_ci_file_is_checked_merged_over_the_defaults(tmp_path: Path) -> None:
    """helm merges a -f file over values.yaml; a partial file is valid, a null that
    removes a required key is not."""
    chart = _copy(tmp_path)
    (chart / "ci" / "partial-values.yaml").write_text("worker:\n  replicas: 2\n", "utf-8")
    assert check_values.main([str(chart)]) == 0
    (chart / "ci" / "partial-values.yaml").write_text("worker:\n  replicas: null\n", "utf-8")
    assert check_values.main([str(chart)]) == 1


def test_a_param_without_schema_entry_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chart = _copy(tmp_path)
    values = chart / "values.yaml"
    values.write_text(
        values.read_text("utf-8").replace(
            "## @param worker.env ", "## @param worker.nothing Gone\n## @param worker.env "
        ),
        "utf-8",
    )
    assert check_values.main([str(chart)]) == 1
    assert "@param worker.nothing has no entry in values.schema.json" in capsys.readouterr().out


def test_a_schema_entry_without_param_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chart = _copy(tmp_path)
    values = chart / "values.yaml"
    values.write_text(
        "\n".join(
            line
            for line in values.read_text("utf-8").splitlines()
            if not line.startswith("## @param podDisruptionBudget.maxUnavailable ")
        )
        + "\n",
        "utf-8",
    )
    assert check_values.main([str(chart)]) == 1
    out = capsys.readouterr().out
    assert "podDisruptionBudget.maxUnavailable has no @param in values.yaml" in out


def test_a_param_names_paths_not_values() -> None:
    text = "## @section X\n## @param a.b The b\n## @param c Ce\nother: 1\n"
    assert check_values.params(text) == ["a.b", "c"]


def test_the_schema_itself_must_be_valid(tmp_path: Path) -> None:
    chart = _copy(tmp_path)
    schema = json.loads((chart / "values.schema.json").read_text("utf-8"))
    schema["properties"]["api"]["type"] = "objekt"
    (chart / "values.schema.json").write_text(json.dumps(schema), "utf-8")
    assert check_values.main([str(chart)]) == 1


def _copy(tmp_path: Path) -> Path:
    chart = tmp_path / "chart"
    (chart / "ci").mkdir(parents=True)
    for name in ("values.yaml", "values.schema.json"):
        shutil.copy(CHART / name, chart / name)
    for path in (CHART / "ci").glob("*-values.yaml"):
        shutil.copy(path, chart / "ci" / path.name)
    return chart
