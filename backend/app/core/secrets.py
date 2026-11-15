"""Secret references (spec 7.1, plan M5 decision 6): a secret is stored as a reference,
never as plaintext.

- `env:NAME`: read from the process environment when used. Only names starting with
  `HERD_AI_`, so a connection cannot be pointed at the database password or the secret
  key itself and send it to a URL of the admin's choosing; the app's own `HERD_AI_`
  settings (`RESERVED_NAMES`, the egress proxy among them) are refused too.
- `enc:<token>`: a Fernet token under a key derived from `HERD_SECRET_KEY`; tokens of
  `HERD_SECRET_KEY_PREVIOUS` still decrypt during a rotation (`rotate`).

The plaintext is formed only by `resolve`, at the moment of a call, as a `SecretStr`
(its repr and str hide the value). Failures say nothing about the value or the key:
`SecretUnavailable` has a fixed message and no cause.
"""

import base64
import os
import re
from enum import StrEnum

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.errors import ValidationFailed

ENV_PREFIX = "env:"
ENC_PREFIX = "enc:"
ENV_NAME = re.compile(r"HERD_AI_[A-Z0-9_]{1,100}")
# The app's own settings with that prefix (`core/config.py`, every `ai_*` field): never
# a connection's key (the egress proxy's URL may carry the proxy's credentials).
RESERVED_NAMES = frozenset(
    f"HERD_{name.upper()}" for name in Settings.model_fields if name.startswith("ai_")
)
MAX_VALUE_CHARS = 4096
# Visible ASCII only: the value goes into an HTTP header.
_VALUE = re.compile(r"[\x21-\x7e]+")
_KDF_INFO = b"to-herd-cats-ai:secret-ref:v1"


class SecretKind(StrEnum):
    ENV = "env"
    ENC = "enc"


class SecretUnavailable(Exception):  # noqa: N818 (a state, not an error class name)
    """The reference cannot be resolved (unset variable, wrong key, malformed)."""

    def __init__(self) -> None:
        super().__init__("secret unavailable")


def env_ref(name: str) -> str:
    """`env:NAME` for an allowed variable name; 422 otherwise."""
    if not _allowed_name(name):
        raise ValidationFailed(code="secrets.env_name_invalid")
    return ENV_PREFIX + name


def encrypt(plaintext: str) -> str:
    """`enc:<token>` under the current key; 422 without a key or for an unusable value."""
    if not _VALUE.fullmatch(plaintext) or len(plaintext) > MAX_VALUE_CHARS:
        raise ValidationFailed(code="secrets.value_invalid")
    keys = _keys()
    if keys is None:
        raise ValidationFailed(code="secrets.key_missing")
    return ENC_PREFIX + keys.encrypt(plaintext.encode()).decode()


def kind_of(ref: str) -> SecretKind:
    return SecretKind.ENV if ref.startswith(ENV_PREFIX) else SecretKind.ENC


def resolve(ref: str) -> SecretStr:
    """The plaintext, for the call about to be made."""
    value = _resolve(ref)
    if value is None:
        raise SecretUnavailable()
    return SecretStr(value)


def rotate(ref: str) -> str:
    """The reference under the current key (`env:` references stay as they are)."""
    if not ref.startswith(ENC_PREFIX):
        return ref
    keys = _keys()
    if keys is None:
        raise SecretUnavailable()
    try:
        return ENC_PREFIX + keys.rotate(ref[len(ENC_PREFIX) :].encode()).decode()
    except (InvalidToken, ValueError):
        pass
    raise SecretUnavailable()


def _resolve(ref: str) -> str | None:
    if ref.startswith(ENV_PREFIX):
        name = ref[len(ENV_PREFIX) :]
        value = os.environ.get(name) if _allowed_name(name) else None
        return value or None
    if ref.startswith(ENC_PREFIX) and (keys := _keys()) is not None:
        try:
            return keys.decrypt(ref[len(ENC_PREFIX) :].encode()).decode()
        except (InvalidToken, ValueError):
            return None
    return None


def _keys() -> MultiFernet | None:
    settings = get_settings()
    if settings.secret_key is None:
        return None
    material = [settings.secret_key, settings.secret_key_previous]
    return MultiFernet([_fernet(k.get_secret_value()) for k in material if k is not None])


def _fernet(material: str) -> Fernet:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_KDF_INFO)
    return Fernet(base64.urlsafe_b64encode(hkdf.derive(material.encode())))


def _allowed_name(name: str) -> bool:
    return ENV_NAME.fullmatch(name) is not None and name not in RESERVED_NAMES
