"""The root docker-compose.yml keeps to Jan's Hostinger rules (plan M9 task 19,
/docs/HOSTINGER.md): a first deploy without any variable, no external network, no
ports, no build or bind mounts, plain YAML for web editors, prefixed Traefik names,
secrets only through files. Static: no Docker needed (CI also runs the stack)."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.stack.init import DB_PASSWORD, GENERATED, PASSWORD_FILE

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.example"
IMAGE = "ghcr.io/janschachtschabel/to-herd-cats-ai:${HERD_IMAGE_TAG:-1.0}"
PREFIX = "herd-"
# Services that run once per deploy and end with exit 0.
ONE_SHOT = {"init", "db-owner"}
_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}")


@pytest.fixture(scope="module")
def text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def stack(text: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(text)
    return loaded


@pytest.fixture(scope="module")
def services(stack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = stack["services"]
    return found


def test_plain_yaml_for_web_editors(text: str) -> None:
    assert "\t" not in text
    for event in yaml.parse(text):
        assert not isinstance(event, yaml.AliasEvent), "no aliases"
        assert getattr(event, "anchor", None) is None, "no anchors"
    assert "<<:" not in text, "no merge keys"
    assert not re.search(r"\$\{[^}]*\$\{", text), "no nested variables"
    assert "$$" not in text, "no shell scripts in the YAML"


def test_every_variable_has_a_default_and_none_is_required(text: str) -> None:
    for match in re.finditer(r"\$\{?[A-Za-z_]", text):
        assert text[match.start() + 1] == "{", "variables are written ${NAME:-default}"
    for name, rest in _VARIABLE.findall(text):
        assert rest.startswith(":-"), f"${{{name}{rest}}} needs a :- default"


def test_every_variable_is_explained_and_empty_in_env_example(text: str) -> None:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    assigned = {
        line.split("=", 1)[0]: (index, line.split("=", 1)[1])
        for index, line in enumerate(lines)
        if line and not line.startswith("#")
    }
    for name, (index, value) in assigned.items():
        assert value == "", f"{name} must be empty in .env.example"
        before = lines[index - 1]
        assert before.startswith("#") or lines[index - 1].split("=", 1)[0] in assigned, name
    used = {name for name, _ in _VARIABLE.findall(text)}
    assert used == set(assigned)


def test_no_build_no_ports_and_one_image(services: dict[str, dict[str, Any]]) -> None:
    for name, service in services.items():
        assert "build" not in service, name
        assert "ports" not in service, f"{name}: Traefik serves 80 and 443, nothing is published"
        if name != "db":
            assert service["image"] == IMAGE, name
    assert "@sha256:" in services["db"]["image"]


def test_only_named_volumes(stack: dict[str, Any], services: dict[str, dict[str, Any]]) -> None:
    named = set(stack["volumes"])
    for name, service in services.items():
        for mount in service.get("volumes", []):
            source = mount.split(":", 1)[0] if isinstance(mount, str) else mount["source"]
            assert source in named, f"{name}: {source} is a bind mount"


def test_the_network_is_named_and_never_external(stack: dict[str, Any]) -> None:
    networks = stack["networks"]
    assert networks["default"] == {"name": "${TRAEFIK_NETWORK:-herd-web}"}
    for name, network in networks.items():
        assert not (network or {}).get("external"), name


def test_everything_waits_for_init(services: dict[str, dict[str, Any]]) -> None:
    for name, service in services.items():
        if name == "init":
            assert service["restart"] == "no"
            continue
        assert service["restart"] == ("no" if name in ONE_SHOT else "unless-stopped"), name
        assert service["depends_on"]["init"] == {
            "condition": "service_completed_successfully",
            "restart": True,
        }, name


def test_traefik_names_are_the_projects_own(services: dict[str, dict[str, Any]]) -> None:
    labels = [label for s in services.values() for label in s.get("labels", [])]
    assert "traefik.enable=true" in labels
    assert "traefik.docker.network=${TRAEFIK_NETWORK:-herd-web}" in labels
    named = 0
    for label in labels:
        parts = label.split("=", 1)[0].split(".")
        if parts[0] == "traefik" and len(parts) > 3 and parts[1] in ("http", "tcp"):
            assert parts[3].startswith(PREFIX), label
            named += 1
    assert named >= 4
    assert "traefik.http.routers.herd-app.rule=Host(`${DOMAIN:-}`)" in labels


def test_secrets_reach_the_app_only_as_files(services: dict[str, dict[str, Any]]) -> None:
    """Every secret is a file init writes; no env value of a running service holds one."""
    written = {f"/db-secret/{DB_PASSWORD}", f"/secrets/{PASSWORD_FILE}"}
    written |= {f"/secrets/{name}" for name in GENERATED}
    for name in ("app", "backup"):
        for key, value in services[name]["environment"].items():
            if re.search("PASSWORD|SECRET|TOKEN|KEY_", key) and "KEEP" not in key:
                assert key.endswith("_FILE"), f"{name}: {key}"
                assert value in written, f"{name}: {key}"
    assert services["db"]["environment"]["POSTGRES_PASSWORD_FILE"].endswith(f"/{DB_PASSWORD}")
    assert services["app"]["environment"]["HERD_BOOTSTRAP_ADMIN_PASSWORD_FILE"] in written


def test_every_deploy_pulls_the_app_image(services: dict[str, dict[str, Any]]) -> None:
    """Compose's default (`missing`) would keep an old :1.0 on a redeploy (review R8)."""
    for name, service in services.items():
        if service["image"] == IMAGE:
            assert service.get("pull_policy") == "always", name


def test_no_long_running_service_of_the_image_disables_its_check(
    services: dict[str, dict[str, Any]],
) -> None:
    """The image has a HEALTHCHECK; `disable: true` fails `up --wait` ("no healthcheck
    configured"). Only the services that end (init, db-owner) may disable it."""
    for name, service in services.items():
        if service["image"] == IMAGE and name not in ONE_SHOT:
            check = service.get("healthcheck", {})
            assert not check.get("disable"), name
    backup = services["backup"]["healthcheck"]["test"]
    assert "HERD_BACKUP_DIR" in " ".join(backup) and "os.W_OK" in " ".join(backup)


def test_the_app_never_connects_as_the_superuser(services: dict[str, dict[str, Any]]) -> None:
    """Review M9b final, F2-1: an archive's dump runs as the app's role, and a superuser
    may run programs on the database host. db-owner makes herd_owner (owner of the
    database, no superuser) as the superuser before app and backup on every deploy;
    they connect as herd_owner and never see the superuser's password."""
    superuser = services["db"]["environment"]["POSTGRES_USER"]
    owner = services["db-owner"]
    assert owner["command"][0] == "db-owner"
    assert owner["depends_on"]["db"] == {"condition": "service_healthy"}
    assert f"/db-secret/{DB_PASSWORD}" in owner["command"]
    assert "/secrets/db_owner_password" in owner["command"]
    for name in ("app", "backup"):
        service = services[name]
        url = service["environment"]["HERD_DATABASE_URL"]
        assert url.startswith("postgresql+asyncpg://herd_owner@"), name
        assert superuser != "herd_owner"
        assert service["environment"]["HERD_DATABASE_PASSWORD_FILE"] == (
            "/secrets/db_owner_password"
        ), name
        mounts = [m.split(":", 1)[0] for m in service["volumes"]]
        assert "db-secret" not in mounts, f"{name} sees the superuser's password"
        assert service["depends_on"]["db-owner"] == {
            "condition": "service_completed_successfully"
        }, name
