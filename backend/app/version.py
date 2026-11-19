"""The application's version: `version` in `pyproject.toml` (the chart's appVersion and
the image tag follow it, `deploy/helm/scripts/check-chart-version.sh`). The image
carries the file next to the code (`/app/pyproject.toml`)."""

import tomllib
from functools import cache
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


@cache
def app_version() -> str:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return str(data["project"]["version"])
