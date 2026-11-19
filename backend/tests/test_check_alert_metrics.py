"""The chart's alerts name only metrics the code exports, and every alert has a rule
test where it fires and one where it stays quiet (plan M9 Task 3)."""

from pathlib import Path
from typing import Any

import yaml

from scripts.check_alert_metrics import (
    RULES,
    alerts,
    exported_names,
    main,
    unknown_metrics,
    untested,
)


def test_every_alert_names_metrics_the_code_exports() -> None:
    assert main([]) == 0
    names = {rule["alert"] for rule in alerts(_load(RULES))}
    assert {"HerdBackupTooOld", "HerdBackupFailing", "HerdOffsiteBackupFailing"} <= names
    assert "HerdBackupNeverRan" in names


def test_a_metric_the_code_does_not_export_is_named() -> None:
    rules = _rules("max(herd_backup_last_succes_timestamp_seconds) > 0")
    assert unknown_metrics(rules, exported_names()) == [
        "HerdX: herd_backup_last_succes_timestamp_seconds is not exported by the code"
    ]
    assert unknown_metrics(_rules("max(kube_pod_info) > 0"), exported_names()) == []


def test_an_alert_without_a_quiet_case_is_named() -> None:
    tests = {"tests": [{"alert_rule_test": [{"alertname": "HerdX", "exp_alerts": [{}]}]}]}
    assert untested(_rules("vector(1)"), tests) == ["HerdX: no rule test where it stays quiet"]


def _rules(expr: str) -> dict[str, Any]:
    return {"groups": [{"rules": [{"alert": "HerdX", "expr": expr}]}]}


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded
