"""Distributed tracing with OpenTelemetry.

Opt-in (``TRACING_ENABLED``). When enabled it:

* installs the FastAPI ASGI tracing middleware,
* auto-instruments SQLAlchemy (database), httpx (outbound HTTP) and Redis,
* adds custom spans for LLM calls and background scheduler ticks,
* exports spans to a configurable backend: **OTLP**, **Jaeger**, **Zipkin** or
  the console.

Every OpenTelemetry import is lazy and individually guarded, so:

* the application boots fine with **no** OpenTelemetry packages installed
  (``TRACING_AVAILABLE is False``), and
* a single missing instrumentation/exporter package degrades gracefully (a
  warning is logged) rather than breaking startup.

``start_as_current_span`` is always safe to call — it is a no-op context manager
when tracing is unavailable or uninitialized.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

try:  # core API + SDK; everything else is imported on demand inside functions.
    from opentelemetry import trace as _trace

    TRACING_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    _trace = None
    TRACING_AVAILABLE = False

_INSTRUMENTATION_SCOPE = "nexora"
_initialized = False
_provider = None


# --- exporter / provider construction ---------------------------------------


def _build_exporter(settings):
    """Return a configured span exporter, or ``None`` for 'none'/unknown."""
    kind = (settings.TRACING_EXPORTER or "otlp").strip().lower()
    endpoint = settings.TRACING_ENDPOINT

    if kind == "none":
        return None

    if kind == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        return ConsoleSpanExporter()

    if kind == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        except Exception as exc:
            logger.warning("tracing_otlp_exporter_unavailable", extra={"error": str(exc)})
            return _console_fallback()
        return OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()

    if kind == "zipkin":
        try:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter
        except Exception as exc:
            logger.warning("tracing_zipkin_exporter_unavailable", extra={"error": str(exc)})
            return _console_fallback()
        return ZipkinExporter(endpoint=endpoint) if endpoint else ZipkinExporter()

    if kind == "jaeger":
        try:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        except Exception as exc:
            logger.warning(
                "tracing_jaeger_exporter_unavailable",
                extra={"error": str(exc), "hint": "pip install opentelemetry-exporter-jaeger"},
            )
            return _console_fallback()
        if endpoint and endpoint.startswith("http"):
            return JaegerExporter(collector_endpoint=endpoint)
        return JaegerExporter()

    logger.warning("tracing_unknown_exporter", extra={"exporter": kind})
    return _console_fallback()


def _console_fallback():
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    return ConsoleSpanExporter()


def _build_provider(settings):
    """Build a TracerProvider with a resource, sampler and exporter pipeline."""
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": settings.APP_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )
    ratio = max(0.0, min(1.0, float(settings.TRACING_SAMPLE_RATIO)))
    provider = TracerProvider(
        resource=resource, sampler=ParentBased(TraceIdRatioBased(ratio))
    )
    exporter = _build_exporter(settings)
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


# --- library instrumentation -------------------------------------------------


def _instrument_libraries(app) -> None:
    # Each instrumentation is independent and best-effort.
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception as exc:
            logger.warning("tracing_fastapi_instrument_failed", extra={"error": str(exc)})

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.database.session import engine

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except Exception as exc:
        logger.warning("tracing_sqlalchemy_instrument_failed", extra={"error": str(exc)})

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.warning("tracing_httpx_instrument_failed", extra={"error": str(exc)})

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception as exc:
        logger.warning("tracing_redis_instrument_failed", extra={"error": str(exc)})


def init_tracing(app=None) -> None:
    """Initialize tracing if enabled and the SDK is available (idempotent)."""
    global _initialized, _provider
    from app.core.config import settings

    if not settings.TRACING_ENABLED:
        return
    if not TRACING_AVAILABLE:
        logger.warning("tracing_enabled_but_sdk_missing")
        return
    if _initialized:
        return
    try:
        _provider = _build_provider(settings)
        _trace.set_tracer_provider(_provider)
        _instrument_libraries(app)
        _initialized = True
        logger.info(
            "tracing_initialized",
            extra={"exporter": settings.TRACING_EXPORTER, "service": settings.OTEL_SERVICE_NAME},
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("tracing_init_failed", extra={"error": str(exc)})


def shutdown_tracing() -> None:
    global _provider, _initialized
    if _provider is not None:
        try:
            _provider.shutdown()
        except Exception:  # pragma: no cover
            pass
    _provider = None
    _initialized = False


# --- custom spans ------------------------------------------------------------


@contextmanager
def start_as_current_span(name: str, attributes: dict | None = None, kind: str | None = None):
    """Start a span as the current span. No-op when tracing is unavailable.

    ``kind`` may be ``"server"``, ``"client"``, ``"producer"``, ``"consumer"``
    or ``"internal"`` (default).
    """
    if not TRACING_AVAILABLE:
        yield None
        return
    tracer = _trace.get_tracer(_INSTRUMENTATION_SCOPE)
    span_kind = {
        "server": _trace.SpanKind.SERVER,
        "client": _trace.SpanKind.CLIENT,
        "producer": _trace.SpanKind.PRODUCER,
        "consumer": _trace.SpanKind.CONSUMER,
        "internal": _trace.SpanKind.INTERNAL,
    }.get((kind or "internal").lower(), _trace.SpanKind.INTERNAL)
    with tracer.start_as_current_span(name, kind=span_kind) as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            try:
                span.record_exception(exc)
                span.set_status(_trace.Status(_trace.StatusCode.ERROR, str(exc)))
            except Exception:  # pragma: no cover
                pass
            raise


def set_span_attribute(key: str, value) -> None:
    """Set an attribute on the current span if one is recording."""
    if not TRACING_AVAILABLE or value is None:
        return
    try:
        span = _trace.get_current_span()
        if span is not None:
            span.set_attribute(key, value)
    except Exception:  # pragma: no cover
        pass
