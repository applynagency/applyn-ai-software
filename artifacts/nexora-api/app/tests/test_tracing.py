"""Tests for distributed tracing (app.observability.tracing).

Skipped entirely when OpenTelemetry is not installed. A single in-memory
TracerProvider is installed once for the module (OTel only honours the first
``set_tracer_provider``); spans are cleared between tests.
"""

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability import tracing

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


@pytest.fixture(autouse=True)
def _clear_spans():
    _exporter.clear()
    yield
    _exporter.clear()


def test_tracing_available():
    assert tracing.TRACING_AVAILABLE is True


def test_start_span_exports_span_with_attributes():
    with tracing.start_as_current_span("test.op", {"foo": "bar", "n": 3}):
        pass
    spans = _exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.op"
    assert spans[0].attributes["foo"] == "bar"
    assert spans[0].attributes["n"] == 3


def test_nested_spans_share_trace():
    with tracing.start_as_current_span("parent"):
        with tracing.start_as_current_span("child"):
            pass
    spans = {s.name: s for s in _exporter.get_finished_spans()}
    assert set(spans) == {"parent", "child"}
    # The child's parent is the parent span; both share one trace id.
    assert spans["child"].context.trace_id == spans["parent"].context.trace_id
    assert spans["child"].parent.span_id == spans["parent"].context.span_id


def test_span_records_exception_and_reraises():
    with pytest.raises(ValueError):
        with tracing.start_as_current_span("boom"):
            raise ValueError("kaboom")
    span = _exporter.get_finished_spans()[0]
    assert span.status.status_code == trace.StatusCode.ERROR
    assert any(e.name == "exception" for e in span.events)


def test_set_span_attribute_on_current_span():
    with tracing.start_as_current_span("with-attr"):
        tracing.set_span_attribute("late.key", "value")
    span = _exporter.get_finished_spans()[0]
    assert span.attributes["late.key"] == "value"


def test_none_attribute_values_are_skipped():
    with tracing.start_as_current_span("skip-none", {"present": "yes", "missing": None}):
        pass
    attrs = _exporter.get_finished_spans()[0].attributes
    assert attrs.get("present") == "yes"
    assert "missing" not in attrs


# --- provider / exporter construction ---------------------------------------


class _Settings:
    APP_VERSION = "1.0.0"
    ENVIRONMENT = "test"
    OTEL_SERVICE_NAME = "nexora-api"
    TRACING_SAMPLE_RATIO = 1.0
    TRACING_ENDPOINT = None

    def __init__(self, exporter):
        self.TRACING_EXPORTER = exporter


def test_build_exporter_none():
    assert tracing._build_exporter(_Settings("none")) is None


def test_build_exporter_console():
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    assert isinstance(tracing._build_exporter(_Settings("console")), ConsoleSpanExporter)


def test_build_exporter_unknown_falls_back_to_console():
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    assert isinstance(tracing._build_exporter(_Settings("bogus")), ConsoleSpanExporter)


def test_build_provider_has_service_resource():
    provider = tracing._build_provider(_Settings("console"))
    assert provider.resource.attributes["service.name"] == "nexora-api"
    assert provider.resource.attributes["service.version"] == "1.0.0"


def test_init_tracing_noop_when_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRACING_ENABLED", False)
    tracing._initialized = False
    tracing.init_tracing(app=None)  # must not raise or initialize
    assert tracing._initialized is False
