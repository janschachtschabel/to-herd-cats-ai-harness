"""Check the chart's alert rules against the code (plan M9 Task 3; the local stand-in
for what `promtool test rules` cannot see):

    uv run python -m scripts.check_alert_metrics [RULES [TESTS]]

- every `herd_*` metric an alert's `expr` names is one the code registers (in
  `app.core.metrics.REGISTRY`, the lazily registered worker gauges included), so a
  renamed metric cannot leave an alert that never fires;
- every alert has a case in the rule tests where it fires and one where it stays quiet.

Metrics of other exporters (`kube_*`) are not checked. Prints each problem; exits 1 if
there is any.
"""

import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

CHART = Path(__file__).resolve().parents[2] / "deploy" / "helm" / "to-herd-cats-ai"
RULES = CHART / "files" / "prometheus-rules.yaml"
TESTS = CHART / "tests" / "rules-test.yaml"
_METRIC = re.compile(r"\bherd_[a-z0-9_]+\b")


def exported_names() -> set[str]:
    """What a process with every role exports: the module-level metrics come with the
    imports, the worker's on their first use."""
    from app.core.metrics import REGISTRY
    from app.modules.agents import external_metrics
    from app.modules.ai.budget_metrics import budget_stops
    from app.modules.automations.metrics import automation_metrics
    from app.modules.backups.metrics import backup_metrics
    from app.web.internal import create_internal_app
    from app.web.public import create_public_app
    from app.worker.metrics import worker_metrics
    from app.worker.runs import run_metrics

    create_public_app()
    create_internal_app()
    for register in (worker_metrics, run_metrics, automation_metrics, backup_metrics):
        register()
    budget_stops()
    external_metrics.count_left_out(0)
    external_metrics.count(external_metrics.CallOutcome.OK, writes=False)
    return set(REGISTRY._names_to_collectors)  # noqa: SLF001 -- every sample name


def alerts(rules: dict[str, Any]) -> list[dict[str, Any]]:
    return [rule for group in rules["groups"] for rule in group["rules"] if "alert" in rule]


def unknown_metrics(rules: dict[str, Any], exported: set[str]) -> list[str]:
    return [
        f"{rule['alert']}: {name} is not exported by the code"
        for rule in alerts(rules)
        for name in sorted(set(_METRIC.findall(rule["expr"])))
        if name not in exported
    ]


def untested(rules: dict[str, Any], tests: dict[str, Any]) -> list[str]:
    fires: set[str] = set()
    quiet: set[str] = set()
    for case in _cases(tests):
        (fires if case.get("exp_alerts") else quiet).add(case["alertname"])
    problems = []
    for name in (rule["alert"] for rule in alerts(rules)):
        if name not in fires:
            problems.append(f"{name}: no rule test where it fires")
        if name not in quiet:
            problems.append(f"{name}: no rule test where it stays quiet")
    return problems


def _cases(tests: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for test in tests["tests"]:
        yield from test.get("alert_rule_test", [])


def main(argv: list[str]) -> int:
    rules_file = Path(argv[0]) if argv else RULES
    tests_file = Path(argv[1]) if len(argv) > 1 else TESTS
    rules = yaml.safe_load(rules_file.read_text(encoding="utf-8"))
    tests = yaml.safe_load(tests_file.read_text(encoding="utf-8"))
    problems = unknown_metrics(rules, exported_names()) + untested(rules, tests)
    for problem in problems:
        print(f"problem {problem}", file=sys.stderr)
    if not problems:
        print(f"ok {len(alerts(rules))} alerts")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
