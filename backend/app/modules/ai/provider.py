"""Talking to a provider in the OpenAI protocol, for the connection check and the
model listing (the agent loop of M5 task 6 has its own client under `app/runtime`).

Every call goes through the egress guard with the rules of the connection's kind. The
key is resolved only here, right before the call, and travels only in the
`Authorization` header. What goes wrong becomes a `CheckStatus`: never the provider's
words (an error body may echo the key), never an exception text, and the HTTP
client's exceptions are dropped (`from None`), since they hold the request and its
headers.
"""

import json
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx

from app.core import egress, secrets
from app.core.egress import EgressBlocked, EgressRules
from app.modules.ai.models import ConnectionKind, ParamFamily, Purpose

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CHECK_PROMPT = "ping"
CHECK_MAX_TOKENS = 16


class CheckStatus(StrEnum):
    OK = "ok"
    UNAUTHORIZED = "unauthorized"  # 401
    PAYMENT_REQUIRED = "payment_required"  # 402
    FORBIDDEN = "forbidden"  # 403
    NOT_FOUND = "not_found"  # 404: base URL or model unknown there
    RATE_LIMITED = "rate_limited"  # 429
    PROVIDER_ERROR = "provider_error"  # any other status
    REDIRECT = "redirect"  # 3xx: not followed
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    BLOCKED = "blocked"  # the egress guard refused the address
    INVALID_RESPONSE = "invalid_response"
    SECRET_UNAVAILABLE = "secret_unavailable"  # noqa: S105 (a state, not a secret)
    NO_MODEL = "no_model"


_BY_STATUS = {
    401: CheckStatus.UNAUTHORIZED,
    402: CheckStatus.PAYMENT_REQUIRED,
    403: CheckStatus.FORBIDDEN,
    404: CheckStatus.NOT_FOUND,
    429: CheckStatus.RATE_LIMITED,
}


class ProviderFailure(Exception):  # noqa: N818
    def __init__(self, status: CheckStatus) -> None:
        self.status = status
        super().__init__(f"provider call failed: {status}")


@dataclass(frozen=True, slots=True)
class Target:
    """What a call needs of a connection, copied out of the row (no session held)."""

    kind: ConnectionKind
    base_url: str
    secret_ref: str | None
    param_family: ParamFamily
    extra_body: dict[str, Any]
    purpose: Purpose


def rules_for(kind: ConnectionKind) -> EgressRules:
    local = kind == ConnectionKind.LOCAL
    return EgressRules(allow_private=local, allow_http=local)


def streams(kind: ConnectionKind) -> bool:
    """Whether calls may stream; the b-api cuts streams anyway (spec 6.3, 7.1)."""
    return kind != ConnectionKind.B_API


async def check(target: Target, model: str, seconds: float) -> CheckStatus:
    """One small call: a chat completion, or an embedding for embedding-only ones."""
    try:
        if target.purpose == Purpose.EMBEDDING:
            body = {**target.extra_body, "model": model, "input": CHECK_PROMPT}
            answer = await _call(target, "POST", "/embeddings", body, seconds)
            ok = isinstance(answer, dict) and isinstance(answer.get("data"), list)
        else:
            body = chat_body(target, model)
            answer = await _call(target, "POST", "/chat/completions", body, seconds)
            ok = isinstance(answer, dict) and isinstance(answer.get("choices"), list)
    except ProviderFailure as failure:
        return failure.status
    return CheckStatus.OK if ok else CheckStatus.INVALID_RESPONSE


def chat_body(target: Target, model: str) -> dict[str, Any]:
    """The check's request: `extra_body`, then what the call itself must set. The
    model field carries a route name for the b-api; nothing streams."""
    return {
        **target.extra_body,
        "model": model,
        "messages": [{"role": "user", "content": CHECK_PROMPT}],
        target.param_family.value: CHECK_MAX_TOKENS,
        "stream": False,
    }


async def list_models(target: Target, seconds: float) -> list[str]:
    """The ids `GET /models` names, as given; `ProviderFailure` otherwise."""
    answer = await _call(target, "GET", "/models", None, seconds)
    data = answer.get("data") if isinstance(answer, dict) else None
    if not isinstance(data, list):
        raise ProviderFailure(CheckStatus.INVALID_RESPONSE)
    ids = [item.get("id") for item in data if isinstance(item, dict)]
    return [i for i in ids if isinstance(i, str) and i.strip()]


async def _call(
    target: Target, method: str, path: str, body: dict[str, Any] | None, seconds: float
) -> Any:
    headers = {"Accept": "application/json"}
    if target.secret_ref is not None:
        try:
            key = secrets.resolve(target.secret_ref)
        except secrets.SecretUnavailable:
            raise ProviderFailure(CheckStatus.SECRET_UNAVAILABLE) from None
        headers["Authorization"] = f"Bearer {key.get_secret_value()}"
    started = time.monotonic()
    status = CheckStatus.OK
    try:
        return await _send(target, method, path, body, headers, seconds)
    except ProviderFailure as failure:
        status = failure.status
        raise
    finally:
        logger.info(
            "ai.provider_call",
            extra={
                "path": path,
                "status": status.value,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )


async def _send(
    target: Target,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    headers: dict[str, str],
    seconds: float,
) -> Any:
    failure: CheckStatus
    try:
        async with egress.client(rules_for(target.kind), timeout=seconds) as http:
            request = http.build_request(method, target.base_url + path, json=body, headers=headers)
            response = await http.send(request, stream=True)
            try:
                if not response.is_success:
                    raise ProviderFailure(_failure_of(response.status_code))
                raw = await _read_limited(response)
            finally:
                await response.aclose()
        return json.loads(raw)
    except ProviderFailure:
        raise
    except EgressBlocked:
        failure = CheckStatus.BLOCKED
    except httpx.TimeoutException:
        failure = CheckStatus.TIMEOUT
    except (httpx.HTTPError, OSError):
        failure = CheckStatus.UNREACHABLE
    except ValueError:  # not JSON, not UTF-8, too large
        failure = CheckStatus.INVALID_RESPONSE
    raise ProviderFailure(failure) from None


def _failure_of(status_code: int) -> CheckStatus:
    if 300 <= status_code < 400:
        return CheckStatus.REDIRECT
    return _BY_STATUS.get(status_code, CheckStatus.PROVIDER_ERROR)


async def _read_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise ValueError("response too large")
        chunks.append(chunk)
    return b"".join(chunks)
