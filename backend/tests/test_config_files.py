"""Secrets from files (`HERD_<NAME>_FILE`, plan M9 task 19): the Hostinger stack's
`init` service writes them into a volume, so that no secret is an env value."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

KEY = "k" * 40
TOKEN = "t" * 40


def _file(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("field", "value"),
    [("secret_key", KEY), ("internal_token", TOKEN), ("bootstrap_admin_password", "Zq8!vR2#mLp4")],
)
def test_a_secret_comes_from_its_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: str
) -> None:
    # A mounted secret often ends with a newline; it is not part of the secret.
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, value + "\n")))
    secret = getattr(Settings(), field)
    assert secret is not None
    assert secret.get_secret_value() == value


@pytest.mark.parametrize("field", ["secret_key", "internal_token", "bootstrap_admin_password"])
def test_a_value_and_its_file_together_are_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    monkeypatch.setenv(f"HERD_{field.upper()}", KEY)
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, KEY)))
    with pytest.raises(ValidationError, match=f"HERD_{field.upper()}_FILE, not both"):
        Settings()


@pytest.mark.parametrize("field", ["secret_key", "internal_token", "bootstrap_admin_password"])
def test_an_unreadable_file_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValidationError, match=f"HERD_{field.upper()}_FILE cannot be read"):
        Settings()


@pytest.mark.parametrize("field", ["secret_key", "internal_token"])
def test_an_empty_file_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    monkeypatch.setenv(f"HERD_{field.upper()}_FILE", str(_file(tmp_path, field, "\n")))
    with pytest.raises(ValidationError, match=f"HERD_{field.upper()}_FILE is empty"):
        Settings()


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


def test_a_bare_scheme_public_url_means_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Hostinger stack passes `HERD_PUBLIC_URL: https://${DOMAIN:-}`; without a
    domain that is a scheme alone, which means "not set" like an empty value."""
    monkeypatch.setenv("HERD_PUBLIC_URL", "https://")
    assert Settings().public_url is None
    monkeypatch.setenv("HERD_PUBLIC_URL", "https://wiki.example")
    assert Settings().public_url == "https://wiki.example"
