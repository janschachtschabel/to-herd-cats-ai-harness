"""Secrets read from files (`HERD_<NAME>_FILE`, plan M9 task 19): a part of `Settings`
(`config.py` inherits it); `get_settings()` stays the one source.

The Hostinger stack's `init` service writes the secrets into a volume, so that none is
an env value (`docker inspect` shows env values). A file's content replaces the value
before any rule of the value applies, so a too short key from a file is refused like
one from the environment. Errors name the variable, never the content.
"""

from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings

# The secrets that may come from a file, and whether an empty file means "not set":
# an empty bootstrap password means no bootstrap, like an empty
# HERD_BOOTSTRAP_ADMIN_PASSWORD; an empty key or token is a broken file.
FILE_SECRETS: dict[str, bool] = {
    "secret_key": False,
    "internal_token": False,
    "bootstrap_admin_password": True,
}


def read_secret_file(path: Path, variable: str, *, empty_ok: bool = False) -> str:
    """The content of `path` without the trailing newline mounted secrets often have;
    a ValueError naming `variable` when it cannot be read or is empty."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) else "not UTF-8 text"
        raise ValueError(f"{variable} cannot be read: {reason}") from None
    content = content.rstrip("\r\n")
    if not content and not empty_ok:
        raise ValueError(f"{variable} is empty")
    return content


class SecretFileSettings(BaseSettings):
    secret_key_file: Path | None = None
    internal_token_file: Path | None = None
    bootstrap_admin_password_file: Path | None = None

    @model_validator(mode="before")
    @classmethod
    def _read_secret_files(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field, empty_ok in FILE_SECRETS.items():
            path = data.get(f"{field}_file")
            if path is None or path == "":
                continue
            variable = f"HERD_{field.upper()}"
            if data.get(field) is not None:
                raise ValueError(f"set {variable} or {variable}_FILE, not both")
            content = read_secret_file(Path(path), f"{variable}_FILE", empty_ok=empty_ok)
            data = {**data, field: content}
        return data
