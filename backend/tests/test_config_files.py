"""Secrets from files (`HERD_<NAME>_FILE`, plan M9 task 19): the Hostinger stack's
`init` service writes them into a volume, so that no secret is an env value."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.config_files import FILE_SECRETS

KEY = "k" * 40
TOKEN = "t" * 40
ALL = [
    "secret_key",
    "internal_token",
    "internal_token_previous",
    "bootstrap_admin_password",
    "s3_secret_access_key",
    "migrate_database_password",
]


def _file(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("secret_key", KEY),
        ("internal_token", TOKEN),
        ("internal_token_previous", TOKEN),
        ("bootstrap_admin_password", "Zq8!vR2#mLp4"),
        ("s3_secret_access_key", "s3-secret-from-a-file"),
        ("migrate_database_password", "owner-pw-from-a-file"),
    ],
)
def test_a_secret_comes_from_its_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: str
) -> None:
    # A mounted secret often ends with a newline; it is not part of the secret.
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, value + "\n")))
    secret = getattr(Settings(), field)
    assert secret is not None
    assert secret.get_secret_value() == value


@pytest.mark.parametrize("field", ALL)
def test_a_value_and_its_file_together_are_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    monkeypatch.setenv(f"HERD_{field.upper()}", KEY)
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, KEY)))
    with pytest.raises(ValidationError, match=f"HERD_{field.upper()}_FILE, not both"):
        Settings()


@pytest.mark.parametrize("field", ALL)
def test_an_unreadable_file_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValidationError, match=f"HERD_{field.upper()}_FILE cannot be read"):
        Settings()


@pytest.mark.parametrize(
    "field",
    [
        "secret_key",
        "internal_token",
        "internal_token_previous",
        "s3_secret_access_key",
        "migrate_database_password",
    ],
)
def test_an_empty_file_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, "\n")))
    with pytest.raises(ValidationError, match=f"HERD_{field.upper()}_FILE is empty"):
        Settings()


def test_the_secret_files_are_one_mechanism() -> None:
    """Every secret read from a file goes through `FILE_SECRETS` (plan M9 tasks 14
    and 19): the S3 secret key too, so it has no reader of its own."""
    assert set(FILE_SECRETS) == set(ALL)


@pytest.mark.parametrize("field", ALL)
def test_an_empty_value_beside_its_file_counts_as_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    """Compose passes an unset variable as `${HERD_X:-}`, an empty value: beside a
    file it is not a second value, the file's content is the secret."""
    monkeypatch.setenv(f"HERD_{field.upper()}", "")
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, KEY)))
    secret = getattr(Settings(), field)
    assert secret is not None
    assert secret.get_secret_value() == KEY


def test_an_empty_bootstrap_password_file_means_no_bootstrap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Like an empty HERD_BOOTSTRAP_ADMIN_PASSWORD: the stack's `init` empties the file
    once the operator clears the one-time password in `.env`."""
    monkeypatch.setenv("HERD_BOOTSTRAP_ADMIN_PASSWORD_FILE", str(_file(tmp_path, "password", "")))
    assert Settings().bootstrap_admin_password.get_secret_value() == ""


def test_the_rules_of_a_value_apply_to_its_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HERD_INTERNAL_TOKEN_FILE", str(_file(tmp_path, "token", "short")))
    with pytest.raises(ValidationError, match="HERD_INTERNAL_TOKEN must be at least 32"):
        Settings()


def test_an_error_never_echoes_the_file_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HERD_SECRET_KEY_FILE", str(_file(tmp_path, "key", "secret-17x")))
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert "secret-17x" not in str(caught.value)


def test_a_copy_of_settings_with_secret_files_stays_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`storage copy --to s3` validates a copy of the settings (`ops/cli_storage.py`):
    the secrets read from files are values there, never a value and its file."""
    for field in ALL:
        monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, KEY)))
    settings = Settings()
    copy = Settings.model_validate(settings.model_dump() | {"storage": "local"})
    for field in ALL:
        assert getattr(copy, field).get_secret_value() == KEY
