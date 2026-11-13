"""AI connections as the API takes and shows them. A secret is written, never shown:
the answer says only whether one is set and which kind of reference it is."""

import json
import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.secrets import SecretKind, kind_of
from app.modules.ai.models import (
    MAX_EXTRA_BODY_CHARS,
    MAX_MODEL_CHARS,
    MAX_MODELS,
    MAX_NAME_CHARS,
    MAX_URL_CHARS,
    AiConnection,
    ConnectionKind,
    DataLocation,
    ParamFamily,
    Purpose,
)
from app.modules.ai.provider import CheckStatus, streams

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
]
ModelName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MODEL_CHARS)
]
BaseUrl = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_URL_CHARS)]
Concurrency = Annotated[int, Field(ge=1, le=100)]
PerMinute = Annotated[int, Field(ge=1, le=100_000)]
# Keys every call sets itself; extra_body may not override them.
RESERVED_BODY_KEYS = frozenset(
    {
        "model",
        "messages",
        "input",
        "stream",
        "tools",
        "tool_choice",
        "max_tokens",
        "max_completion_tokens",
    }
)


# Keys that look like they hold a secret: secrets go into `secret`, which is encrypted
# and never shown, not into extra_body, which is shown and audited.
SECRET_LIKE_KEY = re.compile(
    r"api[_-]?key|secret|passw|authori[sz]ation|bearer|credential|^token$|access[_-]?token",
    re.IGNORECASE,
)


class SecretIn(BaseModel):
    """Either the key itself (`value`, stored encrypted; needs `HERD_SECRET_KEY`) or
    the name of an environment variable `HERD_AI_*` (`env`)."""

    model_config = ConfigDict(extra="forbid")

    value: SecretStr | None = None
    env: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.value is None) == (self.env is None):
            raise ValueError("give either value or env")
        return self


class SecretOut(BaseModel):
    set: bool
    kind: SecretKind | None

    @classmethod
    def of(cls, ref: str | None) -> "SecretOut":
        return cls(set=ref is not None, kind=kind_of(ref) if ref is not None else None)


def _models(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    unique = list(dict.fromkeys(value))
    if len(unique) > MAX_MODELS:
        raise ValueError(f"at most {MAX_MODELS} models")
    return unique


def _extra_body(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if RESERVED_BODY_KEYS & value.keys():
        raise ValueError("extra_body may not set " + ", ".join(sorted(RESERVED_BODY_KEYS)))
    if any(SECRET_LIKE_KEY.search(key) for key in value):
        raise ValueError("extra_body may not hold secrets; use secret")
    if len(json.dumps(value)) > MAX_EXTRA_BODY_CHARS:
        raise ValueError(f"extra_body is longer than {MAX_EXTRA_BODY_CHARS} characters")
    return value


class _ConnectionFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("models", check_fields=False)
    @classmethod
    def _unique_models(cls, value: list[str] | None) -> list[str] | None:
        return _models(value)

    @field_validator("extra_body", check_fields=False)
    @classmethod
    def _body(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _extra_body(value)


class ConnectionCreate(_ConnectionFields):
    """Left out: `base_url` is OpenAI's; `models` is `gpt-6-luna` for `openai`, else
    empty; `param_family` is `max_completion_tokens` for `openai`, else `max_tokens`;
    `data_location` is `local` for `local`, else `external`. The first model is the
    connection's standard model."""

    name: Name
    kind: ConnectionKind = ConnectionKind.OPENAI
    base_url: BaseUrl | None = None
    secret: SecretIn | None = None
    models: list[ModelName] | None = None
    param_family: ParamFamily | None = None
    extra_body: dict[str, Any] | None = None
    supports_tools: bool = True
    data_location: DataLocation | None = None
    max_concurrency: Concurrency = 4
    requests_per_minute: PerMinute = 60
    purpose: Purpose = Purpose.CHAT
    enabled: bool = True


class ConnectionUpdate(_ConnectionFields):
    """Fields left out stay as they are; `secret: null` removes the secret. The kind
    never changes (sending it is 422)."""

    name: Name | None = None
    base_url: BaseUrl | None = None
    secret: SecretIn | None = None
    models: list[ModelName] | None = None
    param_family: ParamFamily | None = None
    extra_body: dict[str, Any] | None = None
    supports_tools: bool | None = None
    data_location: DataLocation | None = None
    max_concurrency: Concurrency | None = None
    requests_per_minute: PerMinute | None = None
    purpose: Purpose | None = None
    enabled: bool | None = None
    version: int

    @model_validator(mode="after")
    def _only_secret_may_be_null(self) -> Self:
        for name in self.model_fields_set - {"secret", "version"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ConnectionOut(BaseModel):
    """`streaming`: whether calls to it may stream (never for `b_api`)."""

    id: uuid.UUID
    name: str
    kind: ConnectionKind
    base_url: str
    secret: SecretOut
    models: list[str]
    param_family: ParamFamily
    extra_body: dict[str, Any]
    supports_tools: bool
    data_location: DataLocation
    max_concurrency: int
    requests_per_minute: int
    purpose: Purpose
    enabled: bool
    streaming: bool
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, c: AiConnection) -> "ConnectionOut":
        return cls(
            id=c.id,
            name=c.name,
            kind=c.kind,
            base_url=c.base_url,
            secret=SecretOut.of(c.secret_ref),
            models=c.models,
            param_family=c.param_family,
            extra_body=c.extra_body,
            supports_tools=c.supports_tools,
            data_location=c.data_location,
            max_concurrency=c.max_concurrency,
            requests_per_minute=c.requests_per_minute,
            purpose=c.purpose,
            enabled=c.enabled,
            streaming=streams(c.kind),
            version=c.version,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )


class CheckIn(BaseModel):
    """`model`: which model (route) to try; left out, the connection's standard model."""

    model_config = ConfigDict(extra="forbid")

    model: ModelName | None = None


class CheckOut(BaseModel):
    """The outcome as a state, never with the provider's own words."""

    status: CheckStatus
    model: str | None
    duration_ms: int


class VersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
