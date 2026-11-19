"""The compose files start with `docker compose up --wait` (README, smoke.sh). Compose
waits for every started service to be healthy, or running when its image has no health
check, or exited 0 when another service waits for it with
`service_completed_successfully`. A service of the app's image (its Dockerfile has a
HEALTHCHECK) that sets `healthcheck: disable: true` fails that wait at once ("container
... has no healthcheck configured"): compose sees a health check configured (`NONE`) and
no health state. So every long-running service of the app's image has a check of its
own, and the backup service's check really answers."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "deploy" / "compose"
APP_IMAGE = "to-herd-cats-ai:"


def _services(*names: str) -> dict[str, dict[str, Any]]:
    """The services of the files merged in order (later files override keys)."""
    merged: dict[str, dict[str, Any]] = {}
    for name in names:
        document = yaml.safe_load((COMPOSE / name).read_text(encoding="utf-8"))
        for service, config in document["services"].items():
            merged.setdefault(service, {}).update(config)
    return merged


def _waited_to_complete(services: dict[str, dict[str, Any]]) -> set[str]:
    done: set[str] = set()
    for config in services.values():
        depends = config.get("depends_on") or {}
        if isinstance(depends, dict):
            for dependency, condition in depends.items():
                if (condition or {}).get("condition") == "service_completed_successfully":
                    done.add(dependency)
    return done


def _health_disabled(config: dict[str, Any]) -> bool:
    check = config.get("healthcheck") or {}
    test = check.get("test")
    return bool(check.get("disable")) or test in (["NONE"], "NONE")


@pytest.mark.parametrize(
    "files", [("compose.yml",), ("compose.yml", "compose.nodes.yml")], ids=["single", "nodes"]
)
def test_up_wait_can_finish_with_every_service_of_the_app_image(files: tuple[str, ...]) -> None:
    services = _services(*files)
    one_shots = _waited_to_complete(services)
    started = {name: c for name, c in services.items() if not c.get("profiles")}
    blocking = sorted(
        name
        for name, config in started.items()
        if str(config.get("image", "")).startswith(APP_IMAGE)
        and _health_disabled(config)
        and name not in one_shots
    )
    assert blocking == [], f"`up --wait` fails on {blocking}: health check disabled"


def _backup_check() -> list[str]:
    test = _services("compose.yml")["backup"]["healthcheck"]["test"]
    assert test[:2] == ["CMD", "python"], test
    return [sys.executable, *test[2:]]


def test_the_backup_service_is_healthy_with_a_writable_backup_directory(
    tmp_path: Path,
) -> None:
    env = {**os.environ, "HERD_BACKUP_DIR": str(tmp_path)}
    assert subprocess.run(_backup_check(), env=env, timeout=30).returncode == 0


def test_the_backup_service_is_unhealthy_without_its_backup_directory(tmp_path: Path) -> None:
    env = {**os.environ, "HERD_BACKUP_DIR": str(tmp_path / "missing")}
    assert subprocess.run(_backup_check(), env=env, timeout=30).returncode != 0
