"""The model a run talks to: Pydantic AI's OpenAI chat model on the connection's base
URL, through the egress guard (`core/egress_x2.py`, httpx2 as the OpenAI SDK uses),
with the key only in the `Authorization` header, no SDK retries (a refused call is
not repeated; spec: 401/402/403 without a retry), no streaming (the b-api cuts
streams; the answer is shown when it is complete), and the connection's parameter
family (`max_tokens` or `max_completion_tokens`) and `extra_body`.

Tests replace `make_model` (Pydantic AI's FunctionModel) or point a connection at the
stub provider (`tests/support/openai_stub.py`).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI
from pydantic import SecretStr
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai_compatible import OpenAICompatibleProvider
from pydantic_ai.settings import ModelSettings

from app.core import egress_x2
from app.core.egress import EgressRules

MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True, slots=True)
class ModelTarget:
    """What a model call needs of a connection, copied out of its row."""

    base_url: str
    rules: EgressRules
    api_key: SecretStr | None
    model: str
    max_completion_tokens: bool  # the parameter family
    extra_body: dict[str, Any] = field(default_factory=dict)
    supports_tools: bool = True
    proxy: str | None = None


@dataclass(slots=True)
class BuiltModel:
    model: Model
    settings: ModelSettings
    close: Callable[[], Awaitable[None]]


async def _nothing() -> None:
    return None


def make_model(target: ModelTarget, timeout: float) -> BuiltModel:
    http = egress_x2.client(target.rules, timeout=timeout, proxy=target.proxy)
    key = target.api_key.get_secret_value() if target.api_key is not None else "none"
    client = AsyncOpenAI(base_url=target.base_url, api_key=key, http_client=http, max_retries=0)
    provider = OpenAICompatibleProvider("herd", openai_client=client)
    profile = OpenAIModelProfile(
        openai_chat_supports_max_completion_tokens=target.max_completion_tokens
    )
    model = OpenAIChatModel(target.model, provider=provider, profile=profile)
    settings: ModelSettings = {
        "max_tokens": MAX_OUTPUT_TOKENS,
        "max_retries": 0,
        "timeout": timeout,
    }
    if target.extra_body:
        settings["extra_body"] = dict(target.extra_body)
    return BuiltModel(model, settings, http.aclose)


def wrap_model(model: Model) -> BuiltModel:
    """A model made elsewhere (tests), with no settings and nothing to close."""
    return BuiltModel(model, {}, _nothing)
