"""
OpenTelemetry integration for Urdu Mushaira.

Provides:
  - Distributed tracing with spans for every major operation
  - Automatic instrumentation of HTTP, database, and LLM calls
  - Metrics collection (latency, token counts, error rates)
  - Exporters to Jaeger, Datadog, or cloud platforms
"""

import logging
import os
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

# Lazy-initialized tracer and meter
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None


def _get_resource() -> Resource:
    """Create OpenTelemetry resource with service metadata."""
    return Resource(
        attributes={
            "service.name": "urdu-mushaira",
            "service.version": "0.2.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
        }
    )


def initialize_otel() -> None:
    """Initialize OpenTelemetry with Jaeger exporter."""
    global _tracer, _meter

    if _tracer is not None:
        return  # Already initialized

    # Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "localhost"),
        agent_port=int(os.getenv("JAEGER_PORT", 6831)),
    )

    # Tracer setup
    trace_provider = TracerProvider(resource=_get_resource())
    trace_provider.add_span_processor(
        BatchSpanProcessor(
            jaeger_exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
        )
    )
    trace.set_tracer_provider(trace_provider)
    _tracer = trace.get_tracer(__name__)

    # Metrics setup (Prometheus)
    prometheus_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(
        resource=_get_resource(),
        metric_readers=[prometheus_reader],
    )
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter(__name__)

    # Auto-instrumentation
    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    logger.info("OpenTelemetry initialized with Jaeger exporter")


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        initialize_otel()
    return _tracer


def get_meter() -> metrics.Meter:
    """Get the global meter instance."""
    global _meter
    if _meter is None:
        initialize_otel()
    return _meter


def create_span(name: str, attributes: Optional[dict] = None) -> trace.Span:
    """
    Create a named span with optional attributes.

    Usage:
        with create_span("poet_composition", {"poet": "Faiz", "position": 5}):
            # code here
    """
    tracer = get_tracer()
    span = tracer.start_span(name)
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    return span


def record_metric(name: str, value: float, unit: str = "1", attributes: Optional[dict] = None) -> None:
    """
    Record a metric value.

    Args:
        name: Metric name (e.g., "poet.composition_time")
        value: Numeric value
        unit: Unit of measurement
        attributes: Optional dict of attributes
    """
    meter = get_meter()
    counter = meter.create_counter(name, unit=unit, description=f"{name} metric")
    if attributes:
        counter.add(value, attributes)
    else:
        counter.add(value)


class OtelSpanContext:
    """Context manager for span creation and attribute setting."""

    def __init__(self, name: str, attributes: Optional[dict] = None):
        self.name = name
        self.attributes = attributes or {}
        self.span: Optional[trace.Span] = None

    def __enter__(self) -> trace.Span:
        self.span = create_span(self.name, self.attributes)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span and exc_type:
            self.span.record_exception(exc_val)
            self.span.set_attribute("error", True)
        if self.span:
            self.span.end()


# Pre-create meters for common operations
_composition_counter = None
_validation_counter = None
_error_counter = None


def get_composition_counter():
    """Get or create counter for successful compositions."""
    global _composition_counter
    if _composition_counter is None:
        meter = get_meter()
        _composition_counter = meter.create_counter(
            "poet.compositions_total",
            unit="1",
            description="Total successful poetry compositions",
        )
    return _composition_counter


def get_validation_counter():
    """Get or create counter for verse validations."""
    global _validation_counter
    if _validation_counter is None:
        meter = get_meter()
        _validation_counter = meter.create_counter(
            "verse.validations_total",
            unit="1",
            description="Total verse validations",
        )
    return _validation_counter


def get_error_counter():
    """Get or create counter for errors."""
    global _error_counter
    if _error_counter is None:
        meter = get_meter()
        _error_counter = meter.create_counter(
            "errors_total",
            unit="1",
            description="Total errors",
        )
    return _error_counter
