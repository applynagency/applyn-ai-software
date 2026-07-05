"""Shared types for the Enterprise Observability Platform."""

from __future__ import annotations

import enum


class IntegrationKind(str, enum.Enum):
    PROMETHEUS = "PROMETHEUS"
    OPENTELEMETRY = "OPENTELEMETRY"
    CLOUDWATCH = "CLOUDWATCH"
    AZURE_MONITOR = "AZURE_MONITOR"
    GCP_MONITORING = "GCP_MONITORING"
    LOKI = "LOKI"
    TEMPO = "TEMPO"
    JAEGER = "JAEGER"
    ZIPKIN = "ZIPKIN"
    ELASTIC = "ELASTIC"
    DATADOG = "DATADOG"
    NEW_RELIC = "NEW_RELIC"
    CUSTOM = "CUSTOM"


class SignalKind(str, enum.Enum):
    METRICS = "METRICS"
    LOGS = "LOGS"
    TRACES = "TRACES"


class SLOObjective(str, enum.Enum):
    AVAILABILITY = "AVAILABILITY"
    LATENCY = "LATENCY"
    SUCCESS_RATE = "SUCCESS_RATE"


SUPPORTED_INTEGRATIONS = [
    IntegrationKind.PROMETHEUS.value,
    IntegrationKind.OPENTELEMETRY.value,
    IntegrationKind.LOKI.value,
    IntegrationKind.TEMPO.value,
    IntegrationKind.JAEGER.value,
    IntegrationKind.ZIPKIN.value,
    IntegrationKind.CLOUDWATCH.value,
    IntegrationKind.AZURE_MONITOR.value,
    IntegrationKind.GCP_MONITORING.value,
    IntegrationKind.ELASTIC.value,
    IntegrationKind.DATADOG.value,
    IntegrationKind.NEW_RELIC.value,
]

GOLDEN_SIGNALS = ["latency", "traffic", "errors", "saturation"]
