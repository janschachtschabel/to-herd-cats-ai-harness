"""OpenTelemetry: tracer provider, propagator selection and the active trace ids.

The propagator follows `OTEL_PROPAGATORS` (default `tracecontext,baggage`; `b3` and
`b3multi` come from opentelemetry-propagator-b3). Spans are exported only when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set; without it they still give every request a trace id.
"""

import os
import secrets
from collections.abc import Mapping
from importlib.metadata import entry_points

from fastapi import FastAPI
from opentelemetry import propagate, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.propagators.textmap import TextMapPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from starlette.types import ASGIApp

from app.core.config import Settings
from app.core.request_context import FreshContext

SERVICE_NAME = "to-herd-cats-ai"
DEFAULT_PROPAGATORS = "tracecontext,baggage"

_provider: TracerProvider | None = None


def current_trace_ids() -> tuple[str, str]:
    """(trace_id, span_id) of the active span as hex; fresh random ids without one."""
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        return trace.format_trace_id(context.trace_id), trace.format_span_id(context.span_id)
    return secrets.token_hex(16), secrets.token_hex(8)


def propagator_from_env(environ: Mapping[str, str] = os.environ) -> TextMapPropagator:
    names = environ.get("OTEL_PROPAGATORS", DEFAULT_PROPAGATORS)
    propagators: list[TextMapPropagator] = []
    for name in (n.strip() for n in names.split(",")):
        if not name or name == "none":
            continue
        found = entry_points(group="opentelemetry_propagator", name=name)
        if not found:
            raise ValueError(f"Unknown propagator in OTEL_PROPAGATORS: {name}")
        propagators.append(next(iter(found)).load()())
    return CompositePropagator(propagators)


def span_exporter_from_env(environ: Mapping[str, str] = os.environ) -> SpanExporter | None:
    if not environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    # Imported lazily: the exporter pulls in protobuf and requests.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    return OTLPSpanExporter()  # reads endpoint, headers and timeout from OTEL_* itself


def _tracer_provider(settings: Settings) -> TracerProvider:
    """One provider per process; it is registered globally for later instrumentations."""
    global _provider
    if _provider is None:
        resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", SERVICE_NAME),
                "deployment.environment.name": settings.environment,
            }
        )
        _provider = TracerProvider(resource=resource)
        exporter = span_exporter_from_env()
        if exporter is not None:
            _provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(_provider)
    return _provider


# Routes whose query carries one-time secrets (the OAuth and OIDC callbacks' code and
# state): no span, since a span records the URL with its query. Regular expressions.
UNTRACED_PATHS = (
    "/api/ai/oauth/callback",
    "/api/ai/oauth/[^/]+/callback",
    "/api/auth/oidc/[^/]+/callback",
)


def configure_tracing(app: FastAPI, settings: Settings) -> None:
    """Every request gets a server span of its own, started in a fresh context
    (`FreshContext` wraps the instrumented stack)."""
    propagate.set_global_textmap(propagator_from_env())
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider(settings),
        exclude_spans=["receive", "send"],
        excluded_urls=",".join(UNTRACED_PATHS),
    )
    instrumented = app.build_middleware_stack

    def build_middleware_stack() -> ASGIApp:
        return FreshContext(instrumented())

    app.build_middleware_stack = build_middleware_stack  # type: ignore[method-assign]
