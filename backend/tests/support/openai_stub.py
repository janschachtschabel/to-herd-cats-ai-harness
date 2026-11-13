"""A local stand-in for a provider that speaks the OpenAI protocol (plan M5: tests
need no real provider).

It answers `POST /v1/chat/completions` (text or tool calls, from a script), `GET
/v1/models`, `POST /v1/embeddings` (deterministic vectors), and can be told to fail
with a status (401, 402, 403, 429, 500, ...), to answer slowly, to answer with
something that is not JSON, or to redirect. Every request is logged with its headers
and body, so a test can search what a provider would have received (review focus 1).
Error bodies echo the request's `Authorization` header on purpose: a provider that
reflects the key must not get it into our answers or logs.

In tests: the `openai_stub` and `openai_tls_stub` fixtures (`tests/factories_ai.py`)
run it in a thread; `state` is shared. As a process (e2e, smoke):
`python -m tests.support.openai_stub --port 8099` with control routes under `/_stub`
(`GET /_stub/log`, `POST /_stub/reset`, `POST /_stub/script`).
"""

import argparse
import asyncio
import datetime
import hashlib
import json
import math
import socket
import tempfile
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route

DEFAULT_MODELS = ["gpt-6-luna", "gpt-6-luna-mini", "text-embedding-3-small"]


@dataclass
class LoggedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: Any
    text: str


@dataclass
class StubState:
    log: list[LoggedRequest] = field(default_factory=list)
    # Chat replies, in order: {"content": "..."} or {"tool_calls": [{"name", "arguments"}]};
    # without one, the reply is "stub reply".
    replies: deque[dict[str, Any]] = field(default_factory=deque)
    # Status codes for the next requests (any route but /_stub).
    failures: deque[int] = field(default_factory=deque)
    delay: float = 0.0
    models: list[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    dimension: int = 8
    redirect_to: str | None = None
    invalid_json: bool = False

    def reset(self) -> None:
        self.log.clear()
        self.replies.clear()
        self.failures.clear()
        self.delay = 0.0
        self.models = list(DEFAULT_MODELS)
        self.dimension = 8
        self.redirect_to = None
        self.invalid_json = False

    def texts(self) -> str:
        """Everything the stub has received, as one string to search."""
        return "\n".join(f"{r.path} {json.dumps(r.headers)} {r.text}" for r in self.log)


def _usage(prompt: str, completion: str) -> dict[str, int]:
    p, c = max(1, len(prompt) // 4), max(1, len(completion) // 4)
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def _vector(text: str, dimension: int) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    raw = [digest[i % len(digest)] - 127.5 for i in range(dimension)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


def _chat(state: StubState, body: dict[str, Any]) -> dict[str, Any]:
    reply = state.replies.popleft() if state.replies else {"content": "stub reply"}
    message: dict[str, Any] = {"role": "assistant", "content": reply.get("content")}
    finish = "stop"
    if calls := reply.get("tool_calls"):
        message["tool_calls"] = [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": c["name"], "arguments": json.dumps(c.get("arguments", {}))},
            }
            for i, c in enumerate(calls)
        ]
        finish = "tool_calls"
    prompt = json.dumps(body.get("messages", []))
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": body.get("model"),
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": _usage(prompt, message.get("content") or json.dumps(calls or "")),
    }


def build_app(state: StubState, prefix: str = "/v1") -> Starlette:
    async def handle(request: Request) -> Response:
        raw = (await request.body()).decode("utf-8", "replace")
        try:
            body: Any = json.loads(raw) if raw else None
        except ValueError:
            body = None
        state.log.append(
            LoggedRequest(request.method, request.url.path, dict(request.headers), body, raw)
        )
        if state.delay:
            await asyncio.sleep(state.delay)
        if state.failures:
            status = state.failures.popleft()
            echo = request.headers.get("authorization", "")
            error = {"message": f"provider says no to {echo}", "type": "stub", "code": status}
            return JSONResponse({"error": error}, status_code=status)
        if state.redirect_to:
            return RedirectResponse(state.redirect_to, status_code=302)
        if state.invalid_json:
            return PlainTextResponse("<html>not json</html>")
        path = request.url.path.removeprefix(prefix)
        if path == "/models" and request.method == "GET":
            data = [{"id": m, "object": "model", "owned_by": "stub"} for m in state.models]
            return JSONResponse({"object": "list", "data": data})
        if path == "/chat/completions" and isinstance(body, dict):
            return JSONResponse(_chat(state, body))
        if path == "/embeddings" and isinstance(body, dict):
            inputs = body.get("input")
            texts = [inputs] if isinstance(inputs, str) else list(inputs or [])
            data = [
                {"object": "embedding", "index": i, "embedding": _vector(t, state.dimension)}
                for i, t in enumerate(texts)
            ]
            usage = {"prompt_tokens": sum(max(1, len(t) // 4) for t in texts)}
            usage["total_tokens"] = usage["prompt_tokens"]
            return JSONResponse({"object": "list", "data": data, "usage": usage})
        return JSONResponse({"error": {"message": "unknown route"}}, status_code=404)

    async def control_log(request: Request) -> Response:
        return JSONResponse([r.__dict__ for r in state.log])

    async def control_reset(request: Request) -> Response:
        state.reset()
        return JSONResponse({})

    async def control_script(request: Request) -> Response:
        script = await request.json()
        state.replies.extend(script.get("replies", []))
        state.failures.extend(script.get("failures", []))
        for name in ("delay", "models", "dimension", "redirect_to", "invalid_json"):
            if name in script:
                setattr(state, name, script[name])
        return JSONResponse({})

    methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    return Starlette(
        routes=[
            Route("/_stub/log", control_log, methods=["GET"]),
            Route("/_stub/reset", control_reset, methods=["POST"]),
            Route("/_stub/script", control_script, methods=["POST"]),
            Route("/{path:path}", handle, methods=methods),
        ]
    )


def self_signed(directory: Path, names: list[str]) -> tuple[Path, Path]:
    """A certificate for `names` (and its key), written to `directory`; it is its own
    CA, so a client trusts it by loading the certificate file."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "stub-cert.pem", directory / "stub-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class OpenAIStub:
    """The stub on 127.0.0.1 in a thread of its own. With `tls_name`, it serves https
    with a certificate for that name; `base_url` then uses the name (tests resolve it
    to 127.0.0.1 through `egress.Network`)."""

    def __init__(self, tls_name: str | None = None) -> None:
        self.state = StubState()
        self.tls_name = tls_name
        self.cert_path: Path | None = None
        self._dir = tempfile.TemporaryDirectory()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self.port: int = self._socket.getsockname()[1]
        ssl: dict[str, Any] = {}
        if tls_name:
            self.cert_path, key_path = self_signed(Path(self._dir.name), [tls_name, "other-ca"])
            ssl = {"ssl_certfile": str(self.cert_path), "ssl_keyfile": str(key_path)}
        # No log config, no level: uvicorn would otherwise reconfigure the process's
        # loggers (`uvicorn.error`), which the app's own tests read.
        config = uvicorn.Config(
            build_app(self.state),
            log_config=None,
            log_level=None,
            lifespan="off",
            access_log=False,
            **ssl,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True
        )

    @property
    def base_url(self) -> str:
        if self.tls_name:
            return f"https://{self.tls_name}:{self.port}/v1"
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> "OpenAIStub":
        self._thread.start()
        for _ in range(500):
            if self._server.started:
                return self
            threading.Event().wait(0.01)
        raise RuntimeError("stub did not start")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
        self._socket.close()
        self._dir.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    uvicorn.run(build_app(StubState()), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
