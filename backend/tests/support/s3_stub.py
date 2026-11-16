"""A local S3-compatible object store for tests (plan M9: never the real network).

Path-style requests (`/<bucket>/<key>`): PUT, GET, HEAD and DELETE of objects (with
`x-amz-meta-*`) and ListObjectsV2 (`?list-type=2`, `prefix`, `max-keys`,
`continuation-token`). Every request must carry a valid AWS Signature Version 4,
checked here from the request as it arrived (its own canonicalisation, not the app's
signer): a wrong signature, an unknown access key, a date more than 15 minutes off, a
body whose SHA-256 differs from `x-amz-content-sha256` or a body without
Content-Length are refused as S3 refuses them. The signer itself is checked against
AWS's published examples (`tests/test_s3_signing.py`).

Scriptable through `state`: `objects`, `failures` (status codes for the next
requests), `cut_put` (abort the next PUT after reading its body: the store keeps
nothing), `log` (method, path, query, headers of each request) and `max_keys` (the
page size it offers at most). `S3Stub` runs it on 127.0.0.1 in a thread of its own;
as a process: `python -m tests.support.s3_stub --port 8333`.
"""

import argparse
import hashlib
import hmac
import socket
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, quote, unquote
from xml.sax.saxutils import escape

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

ACCESS_KEY = "HERDSTUBACCESSKEY"
SECRET_KEY = "herd-stub-secret-key-0123456789abcdef"
BUCKET = "herd-test"
REGION = "us-east-1"
SKEW = timedelta(minutes=15)


@dataclass
class StoredObject:
    data: bytes
    meta: dict[str, str]


@dataclass
class StubLogEntry:
    method: str
    path: str
    query: str
    headers: dict[str, str]


@dataclass
class S3StubState:
    objects: dict[str, StoredObject] = field(default_factory=dict)
    failures: deque[int] = field(default_factory=deque)
    cut_put: bool = False
    log: list[StubLogEntry] = field(default_factory=list)
    max_keys: int = 1000

    def reset(self) -> None:
        self.objects.clear()
        self.failures.clear()
        self.cut_put = False
        self.log.clear()
        self.max_keys = 1000


def _error(status: int, code: str) -> Response:
    body = f'<?xml version="1.0" encoding="UTF-8"?><Error><Code>{code}</Code></Error>'
    return Response(body, status_code=status, media_type="application/xml")


def _encode(value: str) -> str:
    return quote(value, safe="-_.~")


def _signature_problem(request: Request, body_sha256: str | None) -> str | None:
    """The S3 error code for the request's signature, or None when it is valid."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("AWS4-HMAC-SHA256 "):
        return "AccessDenied"
    try:
        fields = dict(
            p.strip().split("=", 1) for p in auth.removeprefix("AWS4-HMAC-SHA256 ").split(",")
        )
        access, day, region, service, terminal = fields["Credential"].split("/")
        signed = fields["SignedHeaders"].split(";")
        given = fields["Signature"]
    except (KeyError, ValueError):
        return "AuthorizationHeaderMalformed"
    if access != ACCESS_KEY:
        return "InvalidAccessKeyId"
    stamp = request.headers.get("x-amz-date", "")
    try:
        at = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return "AccessDenied"
    if abs(datetime.now(UTC) - at) > SKEW:
        return "RequestTimeTooSkewed"
    if "host" not in signed or "x-amz-content-sha256" not in signed:
        return "AccessDenied"
    payload = request.headers.get("x-amz-content-sha256", "")
    if body_sha256 is not None and payload != body_sha256:
        return "XAmzContentSHA256Mismatch"
    raw_path = request.scope.get("raw_path", b"").decode()
    path = "/".join(_encode(unquote(s)) for s in raw_path.split("/"))
    pairs = parse_qsl(request.scope.get("query_string", b"").decode(), keep_blank_values=True)
    query = "&".join(f"{k}={v}" for k, v in sorted((_encode(k), _encode(v)) for k, v in pairs))
    headers = [f"{name}:{' '.join(request.headers.get(name, '').split())}" for name in signed]
    canonical = "\n".join([request.method, path, query, *headers, "", ";".join(signed), payload])
    scope = f"{day}/{region}/{service}/{terminal}"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    key = f"AWS4{SECRET_KEY}".encode()
    for part in (day, region, service, terminal):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    expected = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return None if hmac.compare_digest(expected, given) else "SignatureDoesNotMatch"


def build_app(state: S3StubState) -> Starlette:
    async def bucket_or_object(request: Request) -> Response:
        state.log.append(
            StubLogEntry(
                request.method,
                request.url.path,
                request.url.query,
                dict(request.headers),
            )
        )
        body = b""
        if request.method == "PUT":
            if "content-length" not in request.headers:
                return _error(411, "MissingContentLength")
            body = await request.body()
        body_sha = hashlib.sha256(body).hexdigest() if request.method == "PUT" else None
        if problem := _signature_problem(request, body_sha):
            status = 400 if problem in ("XAmzContentSHA256Mismatch",) else 403
            return _error(status, problem)
        if state.failures:
            return _error(state.failures.popleft(), "InternalError")
        bucket, _, key = request.path_params["path"].partition("/")
        if bucket != BUCKET:
            return _error(404, "NoSuchBucket")
        if not key:
            return (
                _list(state, request)
                if request.method == "GET"
                else _error(405, "MethodNotAllowed")
            )
        return _object(state, request, key, body)

    return Starlette(
        routes=[
            Route(
                "/{path:path}",
                bucket_or_object,
                methods=["GET", "PUT", "HEAD", "DELETE"],
            )
        ]
    )


def _object(state: S3StubState, request: Request, key: str, body: bytes) -> Response:
    if request.method == "PUT":
        if state.cut_put:
            state.cut_put = False
            return _error(500, "InternalError")
        meta = {k: v for k, v in request.headers.items() if k.startswith("x-amz-meta-")}
        state.objects[key] = StoredObject(body, meta)
        return Response(status_code=200)
    if request.method == "DELETE":
        state.objects.pop(key, None)
        return Response(status_code=204)
    stored = state.objects.get(key)
    if stored is None:
        return _error(404, "NoSuchKey") if request.method == "GET" else Response(status_code=404)
    headers = {"content-length": str(len(stored.data)), **stored.meta}
    if request.method == "HEAD":
        return Response(status_code=200, headers=headers)
    return Response(stored.data, status_code=200, headers=headers)


def _list(state: S3StubState, request: Request) -> Response:
    if request.query_params.get("list-type") != "2":
        return _error(400, "InvalidArgument")
    prefix = request.query_params.get("prefix", "")
    limit = min(int(request.query_params.get("max-keys", "1000")), state.max_keys)
    after = request.query_params.get("continuation-token", "")
    keys = sorted(k for k in state.objects if k.startswith(prefix) and k > after)
    page, more = keys[:limit], len(keys) > limit
    contents = "".join(
        f"<Contents><Key>{escape(k)}</Key><Size>{len(state.objects[k].data)}</Size></Contents>"
        for k in page
    )
    token = f"<NextContinuationToken>{escape(page[-1])}</NextContinuationToken>" if more else ""
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>{BUCKET}</Name><KeyCount>{len(page)}</KeyCount>"
        f"<IsTruncated>{'true' if more else 'false'}</IsTruncated>{token}{contents}"
        "</ListBucketResult>"
    )
    return Response(body, media_type="application/xml")


class S3Stub:
    """The stub on 127.0.0.1 (plain http) in a thread of its own."""

    def __init__(self) -> None:
        self.state = S3StubState()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self.port: int = self._socket.getsockname()[1]
        config = uvicorn.Config(
            build_app(self.state), log_config=None, log_level=None, access_log=False
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "S3Stub":
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8333)
    args = parser.parse_args()
    uvicorn.run(build_app(S3StubState()), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
