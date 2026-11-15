"""Check the chart's values files against values.schema.json, without helm.

- values.yaml and every ci/*-values.yaml (each merged over values.yaml, as `helm -f`
  does: a null removes a key) must validate against the schema (JSON Schema draft 7);
- every `## @param <path>` in values.yaml names a property of the schema, and every
  property of the schema has a `@param` of its own, of an ancestor (`api.resources`
  covers its requests and limits) or of a descendant (an object made of params).

    cd backend && uv run python ../deploy/helm/scripts/check_values.py [chart-dir]

Exits 0 when everything holds, 1 otherwise; the problems go to stdout.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

CHART = Path(__file__).resolve().parents[1] / "to-herd-cats-ai"
PARAM = re.compile(r"^## @param (\S+)")


def values_files(chart: Path) -> list[Path]:
    """values.yaml first, then every ci/*-values.yaml in name order."""
    return [chart / "values.yaml", *sorted((chart / "ci").glob("*-values.yaml"))]


def params(text: str) -> list[str]:
    """The paths of the `## @param` lines, in order."""
    return [match.group(1) for line in text.splitlines() if (match := PARAM.match(line))]


def merged(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """`override` laid over `defaults` like helm's -f: maps merge, a null removes the key,
    anything else replaces."""
    result = dict(defaults)
    for key, value in override.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merged(result[key], value)
        else:
            result[key] = value
    return result


def schema_problems(name: str, values: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft7Validator(schema)
    problems = []
    for error in sorted(validator.iter_errors(values), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "(root)"
        problems.append(f"{name}: {path}: {error.message}")
    return problems


def schema_paths(schema: dict[str, Any], prefix: str = "") -> Iterator[str]:
    """Every property path of the schema's nested objects (not of array items)."""
    for key, sub in schema.get("properties", {}).items():
        path = f"{prefix}{key}"
        yield path
        if isinstance(sub, dict):
            yield from schema_paths(sub, f"{path}.")


def param_problems(names: list[str], schema: dict[str, Any]) -> list[str]:
    paths = set(schema_paths(schema))
    problems = [
        f"values.yaml: @param {name} has no entry in values.schema.json"
        for name in names
        if name not in paths
    ]
    documented = set(names)
    for path in sorted(paths):
        parts = path.split(".")
        ancestors = {".".join(parts[:i]) for i in range(1, len(parts))}
        if path in documented or ancestors & documented:
            continue
        if any(name.startswith(f"{path}.") for name in documented):
            continue
        problems.append(f"values.schema.json: {path} has no @param in values.yaml")
    return problems


def check(chart: Path) -> list[str]:
    schema: dict[str, Any] = json.loads((chart / "values.schema.json").read_text("utf-8"))
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as error:
        return [f"values.schema.json: not a valid schema: {error.message}"]
    defaults_text = (chart / "values.yaml").read_text("utf-8")
    defaults: dict[str, Any] = yaml.safe_load(defaults_text) or {}
    problems = param_problems(params(defaults_text), schema)
    for path in values_files(chart):
        loaded = yaml.safe_load(path.read_text("utf-8")) or {}
        values = defaults if path.name == "values.yaml" else merged(defaults, loaded)
        found = schema_problems(path.name, values, schema)
        problems.extend(found)
        print(f"{path.name}: {'ok' if not found else f'{len(found)} problem(s)'}")
    return problems


def main(argv: list[str]) -> int:
    chart = Path(argv[0]) if argv else CHART
    problems = check(chart)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("values OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
