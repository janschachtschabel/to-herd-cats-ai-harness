"""Process logging: one line per record on stdout, JSON by default, text for development.

Every line carries `service`, the active `trace_id`/`span_id` and the fields bound with
`log_context` (org_id, actor, ...). Callers add fields with `extra=`; values are never
taken from headers, cookies or bodies here, so callers must not pass them either.
"""

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

from app.core.config import Settings
from app.core.telemetry import SERVICE_NAME, current_trace_ids

_context: ContextVar[dict[str, Any] | None] = ContextVar("herd_log_context", default=None)
# Fields for the request line, which is written after the endpoint and its dependencies
# have returned: a holder the request middleware owns and code inside the request fills.
_request_fields: ContextVar[dict[str, Any] | None] = ContextVar("herd_request_fields", default=None)

# Attributes every LogRecord has; anything else on a record came in through `extra=`.
_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # uvicorn's ANSI-coloured copy of the message
}


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    """Bind fields (org_id, actor, ...) to every log line written inside the block."""
    token = _context.set({**(_context.get() or {}), **fields})
    try:
        yield
    finally:
        _context.reset(token)


@contextmanager
def request_fields() -> Iterator[dict[str, Any]]:
    """The holder for one request's line (request middleware only)."""
    holder: dict[str, Any] = {}
    token = _request_fields.set(holder)
    try:
        yield holder
    finally:
        _request_fields.reset(token)


def bind_request_fields(**fields: Any) -> None:
    """Put fields on the current request's line too; outside a request this does nothing."""
    holder = _request_fields.get()
    if holder is not None:
        holder.update(fields)


def _fields(record: logging.LogRecord) -> dict[str, Any]:
    trace_id, span_id = current_trace_ids()
    fields: dict[str, Any] = {
        "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
        "level": record.levelname,
        "service": SERVICE_NAME,
        "logger": record.name,
        "trace_id": trace_id,
        "span_id": span_id,
        "message": record.getMessage(),
    }
    fields.update(_context.get() or {})
    fields.update({k: v for k, v in vars(record).items() if k not in _RECORD_ATTRS})
    return fields


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = _fields(record)
        if record.exc_info:
            fields["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(fields, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = _fields(record)
        head = f"{fields.pop('timestamp')} {fields.pop('level'):<8} {fields.pop('logger')}"
        message = fields.pop("message")
        for key in ("service", "span_id"):
            fields.pop(key)
        extras = " ".join(f"{k}={v}" for k, v in fields.items())
        text = f"{head} {message} [{extras}]"
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


class _StdoutHandler(logging.StreamHandler[TextIO]):
    """Writes to whatever sys.stdout is at emit time (pytest swaps it per test)."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def configure_logging(settings: Settings) -> None:
    """Replace the root handlers; idempotent, so it may run again with other settings."""
    handler = _StdoutHandler()
    handler.setFormatter(TextFormatter() if settings.log_format == "text" else JsonFormatter())
    root = logging.getLogger()
    for old in root.handlers[:]:
        if isinstance(old, _StdoutHandler):
            root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
