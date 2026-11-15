"""How the agents demo (`demo_ai.py`) gets a model: `from_env` reads it from the
environment. `HERD_DEMO_AI_KIND` turns it on (`local`, an OpenAI-compatible endpoint
the server reaches over http, such as the OpenAI stub of the tests or a local model
server; `openai`; `openai_compatible`), with `HERD_DEMO_AI_URL` (its base URL;
required except for `openai`), `HERD_DEMO_AI_MODEL` (default `gpt-6-luna`) and
`HERD_DEMO_AI_KEY_ENV` (the name of a `HERD_AI_*` variable of the server that holds the
key; the key itself never passes the demo). `HERD_DEMO_AI_STUB` is the stub's own
address (`python -m tests.support.openai_stub`): the demo then scripts the stub's
replies before every step, so every run ends as described. With a real model, the
same requests go out and the demo waits for each run to end, whatever the model did.
"""

import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from scripts.demo_api import DemoFailed

Script = Callable[[list[dict[str, Any]]], Awaitable[None]]

KINDS = ("local", "openai", "openai_compatible")


async def _nothing() -> None:
    return None


@dataclass
class Ai:
    """The model of the demo. `script`: queues the stub's next replies (none: a real
    model answers); `work`: awaited before every look at a run (a no-op against a
    running installation, whose worker runs them)."""

    base_url: str | None = None
    kind: str = "local"
    model: str = "gpt-6-luna"
    key_env: str | None = None
    script: Script | None = None
    work: Callable[[], Awaitable[None]] = _nothing

    def connection_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"name": "Demo-Modell", "kind": self.kind, "models": [self.model]}
        if self.base_url:
            body["base_url"] = self.base_url
        if self.key_env:
            body["secret"] = {"env": self.key_env}
        return body


def _stub_script(control: str) -> Script:
    async def script(replies: list[dict[str, Any]]) -> None:
        async with httpx.AsyncClient(base_url=control) as stub:
            for path, body in (("/_stub/reset", None), ("/_stub/script", {"replies": replies})):
                response = await stub.post(path, json=body)
                if response.status_code != 200:
                    raise DemoFailed(f"stub {path}: {response.status_code}")

    return script


def from_env(env: Mapping[str, str] = os.environ) -> Ai | None:
    """The demo's model from the environment (module docstring); None: no AI demo."""
    kind = env.get("HERD_DEMO_AI_KIND", "")
    if not kind:
        return None
    url = env.get("HERD_DEMO_AI_URL") or None
    if kind not in KINDS or (url is None and kind != "openai"):
        raise DemoFailed(f"HERD_DEMO_AI_KIND {kind!r} needs one of {KINDS} and HERD_DEMO_AI_URL")
    stub = env.get("HERD_DEMO_AI_STUB")
    return Ai(
        base_url=url,
        kind=kind,
        model=env.get("HERD_DEMO_AI_MODEL") or "gpt-6-luna",
        key_env=env.get("HERD_DEMO_AI_KEY_ENV") or None,
        script=_stub_script(stub.rstrip("/")) if stub else None,
    )
